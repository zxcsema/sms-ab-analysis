SELECT 100 * effect AS "Прирост, п.п.", 100 * ci_lower95 AS "Нижняя граница",
       100 * ci_upper95 AS "Верхняя граница"
FROM sms_ab.experiment_summary;
