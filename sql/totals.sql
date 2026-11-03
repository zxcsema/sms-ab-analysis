SELECT COUNT(*) AS clients_total, SUM(target) AS buyers_total
FROM sms_ab.experiment_users;
