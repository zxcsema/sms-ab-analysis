SELECT 'p-value: рост конверсии в группе SMS' AS "Показатель",
       trim(to_char(p_value, '9.99999EEEE')) AS "Значение"
FROM sms_ab.experiment_summary
UNION ALL
SELECT 'Вывод при уровне значимости 5%',
       CASE WHEN p_value < alpha THEN 'Рост конверсии статистически значим'
            ELSE 'Статистически значимый рост не подтверждён' END
FROM sms_ab.experiment_summary;
