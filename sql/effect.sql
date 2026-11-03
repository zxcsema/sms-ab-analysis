WITH groups AS (
    SELECT treatment_flg, AVG(target::double precision) AS cr
    FROM sms_ab.experiment_users
    GROUP BY treatment_flg
)
SELECT 100.0 * (b.cr - a.cr) AS effect_pp,
       100.0 * (b.cr / a.cr - 1) AS relative_lift_pct
FROM groups a CROSS JOIN groups b
WHERE a.treatment_flg = 0 AND b.treatment_flg = 1;
