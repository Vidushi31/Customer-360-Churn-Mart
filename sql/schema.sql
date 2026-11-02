PRAGMA foreign_keys = ON;

-- RAW STAGING: one record per source customer; all fields retained as text.
CREATE TABLE raw_telco (
    customer_id TEXT PRIMARY KEY,
    gender TEXT, senior_citizen TEXT, partner TEXT, dependents TEXT,
    tenure_months TEXT, phone_service TEXT, multiple_lines TEXT,
    internet_service TEXT, online_security TEXT, online_backup TEXT,
    device_protection TEXT, tech_support TEXT, streaming_tv TEXT,
    streaming_movies TEXT, contract_type TEXT, paperless_billing TEXT,
    payment_method TEXT, monthly_charges TEXT, total_charges TEXT, churn TEXT
);

-- CLEAN LAYER: validated, correctly typed and business-ready records.
CREATE TABLE stg_telco_clean (
    customer_id TEXT PRIMARY KEY,
    gender TEXT NOT NULL,
    senior_citizen INTEGER NOT NULL CHECK (senior_citizen IN (0,1)),
    partner INTEGER NOT NULL CHECK (partner IN (0,1)),
    dependents INTEGER NOT NULL CHECK (dependents IN (0,1)),
    tenure_months INTEGER NOT NULL CHECK (tenure_months >= 0),
    tenure_band TEXT NOT NULL,
    phone_service INTEGER NOT NULL CHECK (phone_service IN (0,1)),
    multiple_lines INTEGER NOT NULL CHECK (multiple_lines IN (0,1)),
    internet_service TEXT NOT NULL,
    online_security INTEGER NOT NULL CHECK (online_security IN (0,1)),
    online_backup INTEGER NOT NULL CHECK (online_backup IN (0,1)),
    device_protection INTEGER NOT NULL CHECK (device_protection IN (0,1)),
    tech_support INTEGER NOT NULL CHECK (tech_support IN (0,1)),
    streaming_tv INTEGER NOT NULL CHECK (streaming_tv IN (0,1)),
    streaming_movies INTEGER NOT NULL CHECK (streaming_movies IN (0,1)),
    total_services INTEGER NOT NULL CHECK (total_services BETWEEN 0 AND 9),
    contract_type TEXT NOT NULL,
    paperless_billing INTEGER NOT NULL CHECK (paperless_billing IN (0,1)),
    payment_method TEXT NOT NULL,
    monthly_charges REAL NOT NULL CHECK (monthly_charges >= 0),
    total_charges REAL NOT NULL CHECK (total_charges >= 0),
    churn_flag INTEGER NOT NULL CHECK (churn_flag IN (0,1))
);

-- NORMALIZED OPERATIONAL REPRESENTATION (customer attributes separated by topic).
-- The source has only one snapshot; these are one-to-one profiles per customer.
CREATE TABLE customer_3nf (
    customer_id TEXT PRIMARY KEY,
    gender TEXT NOT NULL,
    senior_citizen INTEGER NOT NULL,
    partner INTEGER NOT NULL,
    dependents INTEGER NOT NULL,
    churn_flag INTEGER NOT NULL
);
CREATE TABLE contract_3nf (
    customer_id TEXT PRIMARY KEY REFERENCES customer_3nf(customer_id),
    contract_type TEXT NOT NULL,
    tenure_months INTEGER NOT NULL
);
CREATE TABLE service_3nf (
    customer_id TEXT PRIMARY KEY REFERENCES customer_3nf(customer_id),
    phone_service INTEGER NOT NULL,
    multiple_lines INTEGER NOT NULL,
    internet_service TEXT NOT NULL,
    online_security INTEGER NOT NULL,
    online_backup INTEGER NOT NULL,
    device_protection INTEGER NOT NULL,
    tech_support INTEGER NOT NULL,
    streaming_tv INTEGER NOT NULL,
    streaming_movies INTEGER NOT NULL
);
CREATE TABLE billing_3nf (
    customer_id TEXT PRIMARY KEY REFERENCES customer_3nf(customer_id),
    paperless_billing INTEGER NOT NULL,
    payment_method TEXT NOT NULL,
    monthly_charges REAL NOT NULL,
    total_charges REAL NOT NULL
);

-- INDEPENDENT DATA MART: dimensions loaded directly from the project cleaning pipeline
-- rather than from any pre-existing enterprise data warehouse.
CREATE TABLE dim_customer (
    customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL UNIQUE,
    gender TEXT NOT NULL,
    senior_citizen INTEGER NOT NULL,
    partner INTEGER NOT NULL,
    dependents INTEGER NOT NULL
);
CREATE TABLE dim_contract (
    contract_key INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_type TEXT NOT NULL UNIQUE
);
CREATE TABLE dim_service (
    service_key INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_service INTEGER NOT NULL,
    multiple_lines INTEGER NOT NULL,
    internet_service TEXT NOT NULL,
    online_security INTEGER NOT NULL,
    online_backup INTEGER NOT NULL,
    device_protection INTEGER NOT NULL,
    tech_support INTEGER NOT NULL,
    streaming_tv INTEGER NOT NULL,
    streaming_movies INTEGER NOT NULL,
    total_services INTEGER NOT NULL,
    UNIQUE(phone_service, multiple_lines, internet_service, online_security,
           online_backup, device_protection, tech_support, streaming_tv, streaming_movies)
);
CREATE TABLE fact_customer_month (
    customer_key INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    contract_key INTEGER NOT NULL REFERENCES dim_contract(contract_key),
    service_key INTEGER NOT NULL REFERENCES dim_service(service_key),
    snapshot_month TEXT NOT NULL,
    tenure_months INTEGER NOT NULL,
    tenure_band TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    paperless_billing INTEGER NOT NULL,
    monthly_charges REAL NOT NULL,
    total_charges REAL NOT NULL,
    churn_flag INTEGER NOT NULL CHECK (churn_flag IN (0,1)),
    PRIMARY KEY (customer_key, snapshot_month)
);
CREATE INDEX idx_fact_contract ON fact_customer_month(contract_key);
CREATE INDEX idx_fact_service ON fact_customer_month(service_key);
CREATE INDEX idx_fact_tenure_band ON fact_customer_month(tenure_band);
CREATE INDEX idx_fact_payment ON fact_customer_month(payment_method);

-- Business-facing Customer 360 semantic view: 1 customer per imported snapshot.
CREATE VIEW v_churn_360 AS
SELECT f.snapshot_month, c.customer_id, c.gender, c.senior_citizen, c.partner,
       c.dependents, ct.contract_type, f.tenure_months, f.tenure_band,
       s.phone_service, s.multiple_lines, s.internet_service, s.online_security,
       s.online_backup, s.device_protection, s.tech_support, s.streaming_tv,
       s.streaming_movies, s.total_services,
       f.payment_method, f.paperless_billing, f.monthly_charges,
       f.total_charges, f.churn_flag
FROM fact_customer_month AS f
JOIN dim_customer AS c ON f.customer_key = c.customer_key
JOIN dim_contract AS ct ON f.contract_key = ct.contract_key
JOIN dim_service AS s ON f.service_key = s.service_key;
