SELECT CASE treatment_flg WHEN 0 THEN 'A: без SMS' ELSE 'B: SMS' END AS group_name,
       COUNT(*) AS clients,
       SUM(target) AS buyers,
       100.0 * AVG(target::double precision) AS conversion_pct
FROM sms_ab.experiment_users
GROUP BY treatment_flg
ORDER BY treatment_flg;
