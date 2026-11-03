"""Перенос исходных клиентов и рассчитанных в ноутбуке таблиц в схему sms_ab."""
from hashlib import sha256
from io import StringIO
from pathlib import Path
import json
import os

import numpy as np
import pandas as pd
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def copy_frame(cur, frame, table):
    buffer = StringIO()
    frame.to_csv(buffer, index=False)
    buffer.seek(0)
    columns = sql.SQL(", ").join(map(sql.Identifier, frame.columns))
    query = sql.SQL(
        "COPY sms_ab.{} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    ).format(sql.Identifier(table), columns)
    cur.copy_expert(query.as_string(cur), buffer)


def main():
    metadata = json.loads((ROOT / "results/analysis_metadata.json").read_text())
    data_path = ROOT / "data/uplift_train.csv.gz"
    source_hash = sha256(data_path.read_bytes()).hexdigest()
    if source_hash != metadata["source_sha256"]:
        raise ValueError("Исходный CSV изменился: сначала повторно выполните ноутбук.")

    users = pd.read_csv(data_path, dtype={"client_id": "string"})
    users = users[["client_id", "treatment_flg", "target"]]
    if users.isna().any().any():
        raise ValueError("В данных есть пропуски: загрузка отменена.")
    if users["client_id"].duplicated().any():
        raise ValueError("В данных есть повторные client_id: загрузка отменена.")
    if not users[["treatment_flg", "target"]].isin([0, 1]).all().all():
        raise ValueError("treatment_flg и target должны принимать значения 0 или 1.")

    summary_frame = pd.read_csv(ROOT / "results/experiment_summary.csv")
    expected = pd.read_csv(ROOT / "results/group_summary.csv")

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute((ROOT / "sql/schema.sql").read_text())
            # Одна транзакция: читатели не увидят наполовину загруженные таблицы.
            cur.execute("TRUNCATE sms_ab.experiment_users, sms_ab.experiment_summary")
            copy_frame(cur, users, "experiment_users")
            copy_frame(cur, summary_frame, "experiment_summary")
            cur.execute("""
                SELECT treatment_flg, COUNT(*), SUM(target), AVG(target::float8)
                FROM sms_ab.experiment_users
                GROUP BY treatment_flg
                ORDER BY treatment_flg
            """)
            actual = cur.fetchall()
            expected_values = expected[
                ["treatment_flg", "clients", "buyers", "conversion"]
            ].to_numpy(float)
            np.testing.assert_allclose(
                np.array(actual, dtype=float), expected_values, rtol=1e-12
            )
            summary = summary_frame.iloc[0]
            np.testing.assert_allclose(
                actual[1][3] - actual[0][3], summary["effect"], atol=1e-12
            )

            reader = os.environ["REDASH_PG_USER"]
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (reader,))
            reader_exists = cur.fetchone() is not None
            # Этот проект управляет только собственной технической ролью.
            if reader == "sms_ab_reader":
                verb = "ALTER" if reader_exists else "CREATE"
                cur.execute(
                    sql.SQL(verb + " ROLE {} LOGIN PASSWORD %s").format(
                        sql.Identifier(reader)
                    ),
                    (os.environ["REDASH_PG_PASSWORD"],),
                )
                cur.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA sms_ab TO {}").format(
                        sql.Identifier(reader)
                    )
                )
                cur.execute(
                    sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA sms_ab TO {}").format(
                        sql.Identifier(reader)
                    )
                )
                cur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES IN SCHEMA sms_ab "
                        "GRANT SELECT ON TABLES TO {}"
                    ).format(sql.Identifier(reader))
                )

            cur.execute("SELECT COUNT(*) FROM sms_ab.experiment_users")
            clients = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sms_ab.experiment_summary")
            if cur.fetchone()[0] != 1:
                raise ValueError("Ожидалась одна итоговая оценка эксперимента.")

    print(f"Загружено клиентов: {clients:,}. Итоговая оценка: 1 строка.")
    print("Агрегаты и эффект совпадают с ноутбуком.")


if __name__ == "__main__":
    main()
