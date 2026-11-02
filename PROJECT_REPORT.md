# Project 5 — Customer 360 and Churn Mart for a Telecom Operator

## 1. Objective
Build an **independent customer-churn data mart** over the IBM Telco sample. Deliver validated customer data, a dimensional model, and a retention dashboard that segments churn by contract, tenure, internet service, and payment method.

## 2. Roles and hand-offs (deliverable)
| Pipeline phase | Main role | Responsibility | Handoff |
| --- | --- | --- | --- |
| Source ingestion | Data Engineer | Acquire source CSV and load `raw_telco` unchanged in meaning | Raw dataset + ingestion record to Data Engineer (transformation) |
| Cleaning, normalization and ETL | Data Engineer | Validate types, repair known blanks, create 3NF profiles, load dimensions and fact | Validated SQLite mart + SQL schema + ETL log to BI Developer |
| Dashboard and metric definitions | BI Developer | Connect the mart, define churn rate, filters, charts and target scorecard | Interactive Streamlit dashboard + metric specification to Analyst |
| Churn insights | Analyst | Compare segments, flag high-churn cohorts and recommend testable offers | Retention insights and recommendations to retention manager |

## 3. Architecture, independent vs dependent mart (deliverable)

```text
IBM CSV
   ↓
raw_telco (raw text staging)
   ↓  Python ETL
stg_telco_clean (types, standardized flags, features)
   ↓
3NF customer_3nf ─ contract_3nf ─ service_3nf ─ billing_3nf
   ↓
Independent churn mart: dim_customer + dim_contract + dim_service
                        + fact_customer_month
   ↓
v_churn_360 → Streamlit dashboard / SQL reporting / CSV exports
```

**Independent mart (implemented):** The mart is populated directly from this project's cleaned source/3NF tables. There is no preexisting enterprise warehouse dependency. This allows rapid prototyping, but separate departments could later define customers or contract types differently.

**Dependent mart (alternative):** A centralized enterprise data warehouse would first ingest and standardize CRM, billing, and product-service data; the churn mart would then consume governed dimensions and facts from that warehouse, improving consistency and shared lineage but adding upstream dependency and implementation cost.

## 4. Normalized 3NF and star-schema data model (deliverable)

**3NF conceptual entities** (each source row is one customer at a single snapshot):
- `customer_3nf(customer_id PK, gender, senior_citizen, partner, dependents, churn_flag)`
- `contract_3nf(customer_id PK/FK, contract_type, tenure_months)`
- `service_3nf(customer_id PK/FK, phone_service, multiple_lines, internet_service, online_security, online_backup, device_protection, tech_support, streaming_tv, streaming_movies)`
- `billing_3nf(customer_id PK/FK, paperless_billing, payment_method, monthly_charges, total_charges)`

Each table stores attributes about a single logical entity/profile; customer IDs link the tables. The single-row-per-customer IBM source does not support real transaction histories, but this is a meaningful 3NF-style decomposition for this exercise.

**Dimensional mart:**
- `dim_customer(customer_key PK, customer_id unique, gender, senior_citizen, partner, dependents)`
- `dim_contract(contract_key PK, contract_type unique)`
- `dim_service(service_key PK, internet_service, phone_service, multiple_lines, six add-on flags, total_services)`
- `fact_customer_month(customer_key FK, contract_key FK, service_key FK, snapshot_month, tenure_months, tenure_band, payment_method, paperless_billing, monthly_charges, total_charges, churn_flag)`

Fact primary key is `(customer_key, snapshot_month)`; its grain is **one customer per imported snapshot**. `snapshot_month` records the ETL's chosen **load-period label**, not a verified historical month. Do not use it to construct a monthly churn trend. Contract and service dimensions describe observed categories/profiles; payment method is a degenerate reporting attribute on the fact for convenience.

SQL DDL: `sql/schema.sql`. Reproducible queries: `sql/analysis_queries.sql`.

## 5. Cleaning and ETL vs ELT (deliverable)

**Cleaning rules:**
1. Read every CSV column as text in the raw staging layer.
2. Convert numeric fields (`tenure`, `MonthlyCharges`, `TotalCharges`, `SeniorCitizen`).
3. Standardize Yes/No to 1/0, including "No internet service" / "No phone service" service-option values. Preserve `internet_service` as `No`, `DSL`, or `Fiber optic`.
4. Replace blank/non-numeric `TotalCharges` with **0 only when `tenure = 0`**; fail on unexplained blanks for other tenures rather than invent amounts.
5. Create `tenure_band`: `0-12`, `13-24`, `25-48`, `49+` months.
6. Create `total_services`: the number of active **phone**, **multiple lines**, **internet access** and six internet add-on services, so it ranges from 0 to 9.
7. Reject blank/duplicate customer IDs, invalid flags and negative charges.

**ETL selected:** Python **extracts** the CSV, **transforms** and validates it with pandas, then **loads** SQLite 3NF and star schema. ETL is straightforward for this small (~7,043-row) one-time source and makes data-quality validation explicit before exposing the mart.

**ELT alternative:** Ingest raw files into a capable cloud warehouse first, then use SQL to clean and transform within that warehouse. This is preferable for large sources, incremental loads, centralized lineage and many consuming teams. For this two-hour local demonstration, ETL has fewer dependencies.

## 6. Churn KPI and reporting logic (deliverable)

`Churn rate (%) = 100 * SUM(churn_flag) / COUNT(customers)`.

The `churn_flag` is 1 for Churn=Yes and 0 for Churn=No. For each chart, group by the named category **using the same reporting view `v_churn_360`**; therefore the category denominators are the number of customers in that category. The KPI scorecard compares the measured rate against a **user-set illustrative 20% target** (not a documented IBM target).

The dashboard allows filtering by contract, tenure band, internet service, and payment method, and downloading the filtered view. `outputs/churn_by_*.csv` supplies reusable SQL/Excel-style scorecards.

## 7. Interpretation and action

After running `py etl.py`, inspect `outputs/churn_by_*.csv` and the four dashboard charts. Identify high-churn segments while comparing **group sizes**; prioritize test campaigns for sufficiently large, high-churn cohorts. Example actions: an optional contract-commitment offer for month-to-month subscribers, service-quality outreach to dissatisfied internet segments, and onboarding interventions for short-tenure customers. Test offers with randomized holdouts rather than treating correlations as causation.

**Limitations:** The IBM dataset is fictional and cross-sectional, offers no customer activity history or exact churn dates, and does not establish why customers churned. This is a descriptive customer-360/reporting mart, not a trained churn-prediction model.

## 8. Evidence and hand-in checklist

- [ ] `PROJECT_REPORT.md` — role mapping, architecture, normalized model, ETL vs ELT rationale, insight framework
- [ ] `sql/schema.sql` — raw, cleaned, 3NF, dim and fact DDL
- [ ] `etl.py` and `verify.py` — working implementation and checks
- [ ] `dashboard.py` — interactive churn dashboard
- [ ] `telecom_churn.db` — built database (created when ETL runs)
- [ ] `outputs/summary.csv`, four `churn_by_*.csv`, `etl_run_log.txt` — ETL evidence
- [ ] Screenshots: `py verify.py` output, SQL view or schema, dashboard scorecard + four charts
- [ ] Two or three short retention insights based on actual segment results

## 9. Dataset attribution

Source: IBM, [`telco-customer-churn-on-icp4d` repository](https://github.com/IBM/telco-customer-churn-on-icp4d), [`data/Telco-Customer-Churn.csv`](https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv). Repository license: Apache 2.0. This project does not redistribute the CSV; the script downloads it on first run unless you supply it manually.
