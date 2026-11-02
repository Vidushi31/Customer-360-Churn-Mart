-- Run these in DB Browser for SQLite or another SQLite SQL client after: py etl.py
-- Churn is measured as a proportion of customers with churn_flag = 1.

-- 1) Validation: counts of pipeline layers
SELECT 'raw_telco' AS layer, COUNT(*) AS customers FROM raw_telco
UNION ALL SELECT 'stg_telco_clean', COUNT(*) FROM stg_telco_clean
UNION ALL SELECT 'fact_customer_month', COUNT(*) FROM fact_customer_month;

-- 2) Overall churn and target check: target=20% is illustrative only
SELECT COUNT(*) AS customers, SUM(churn_flag) AS churned,
       ROUND(AVG(churn_flag) * 100, 2) AS churn_rate_pct,
       CASE WHEN AVG(churn_flag) * 100 <= 20 THEN 'On target' ELSE 'Above target' END AS target_status
FROM v_churn_360;

-- 3) Churn by contract type
SELECT contract_type, COUNT(*) AS customers, SUM(churn_flag) AS churned,
       ROUND(AVG(churn_flag) * 100, 2) AS churn_rate_pct
FROM v_churn_360
GROUP BY contract_type ORDER BY churn_rate_pct DESC;

-- 4) Churn by tenure band
SELECT tenure_band, COUNT(*) AS customers, SUM(churn_flag) AS churned,
       ROUND(AVG(churn_flag) * 100, 2) AS churn_rate_pct
FROM v_churn_360
GROUP BY tenure_band
ORDER BY CASE tenure_band WHEN '0-12 months' THEN 1 WHEN '13-24 months' THEN 2
    WHEN '25-48 months' THEN 3 ELSE 4 END;

-- 5) Churn by internet service
SELECT internet_service, COUNT(*) AS customers, SUM(churn_flag) AS churned,
       ROUND(AVG(churn_flag) * 100, 2) AS churn_rate_pct
FROM v_churn_360
GROUP BY internet_service ORDER BY churn_rate_pct DESC;

-- 6) Churn by payment method
SELECT payment_method, COUNT(*) AS customers, SUM(churn_flag) AS churned,
       ROUND(AVG(churn_flag) * 100, 2) AS churn_rate_pct
FROM v_churn_360
GROUP BY payment_method ORDER BY churn_rate_pct DESC;

-- 7) Segments with at least 50 customers (avoid interpreting tiny groups)
SELECT contract_type, internet_service, tenure_band,
       COUNT(*) AS customers, SUM(churn_flag) AS churned,
       ROUND(AVG(churn_flag) * 100, 2) AS churn_rate_pct
FROM v_churn_360
GROUP BY contract_type, internet_service, tenure_band
HAVING COUNT(*) >= 50 ORDER BY churn_rate_pct DESC LIMIT 10;
