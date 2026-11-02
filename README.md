# Project 5: Customer 360 and Churn Mart (IBM Telecom)

A ready-to-run **Windows CMD-friendly** mini-project. No MySQL server is needed: **SQLite** is created automatically, and the **Streamlit** dashboard runs in a browser.

## 0. What you need

- Windows 10/11 computer with **Python 3.10 or newer** (`py --version` in CMD)
- Internet for `pip` and (only on first run) downloading the sample dataset
- Any editor (VS Code is optional)

Dataset: [IBM GitHub CSV](https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv) ([project repository](https://github.com/IBM/telco-customer-churn-on-icp4d)). IBM data has **7,043 customer rows**, **21 original fields**. The source is not bundled; ETL downloads the file when it does not exist.

## Step-by-step Windows CMD instructions

### Step 1 — Extract the project ZIP

Right-click the ZIP → **Extract All**. Open the unzipped `telecom_customer_360_churn_project` folder in File Explorer. Click the File Explorer address bar, type `cmd` and press Enter. A terminal opens in exactly that folder.

### Step 2 — Check Python

```bat
py --version
```

If that fails, install Python from [python.org](https://www.python.org/downloads/windows/) and ensure the Python Launcher is enabled. Reopen CMD.

### Step 3 — Install dashboard libraries

```bat
py -m pip install -r requirements.txt
```

### Step 4 — Build all database layers (ETL)

```bat
py etl.py
```

The script downloads the IBM CSV to `data\Telco-Customer-Churn.csv` if necessary, validates and cleans it, and builds `telecom_churn.db` with raw, cleaned, 3NF and star-schema tables. It also exports summary/segment CSV reports in `outputs\`.

**Expected output** (with the original IBM CSV): approximately

```text
SUCCESS: ETL finished
Rows loaded (raw, cleaned, fact): 7043 / 7043 / 7043
Missing TotalCharges repaired for tenure=0: 11
Churned: 1869
Overall churn: 26.54%
```

Actual load month printed is **a processing label**; the historical date is not in the IBM data.

**Offline data option:** If automatic download fails, download the [CSV directly](https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv) in your browser and save it at `data\Telco-Customer-Churn.csv`, then repeat `py etl.py`.

### Step 5 — Verify tables and churn calculations

```bat
py verify.py
```

Expected: `ALL CHECKS PASSED` after a table-by-table count and churn-by-contract report. **Take a screenshot for your project evidence.**

If you want screenshot evidence from a graphical SQL tool, you can optionally install [DB Browser for SQLite](https://sqlitebrowser.org/), open `telecom_churn.db`, go to **Execute SQL**, and paste queries from `sql\analysis_queries.sql`. Screenshot the results of the `SELECT ... FROM v_churn_360` and overall churn query. **DB Browser is optional.**

### Step 6 — Launch the dashboard

```bat
py -m streamlit run dashboard.py
```

Wait for CMD to show the local link and open it, normally **http://localhost:8501**. If it doesn't open automatically, paste the displayed `Local URL` in your browser.

Use sidebar filters and adjustable churn target. The page shows:

- Customers, churned customers, churn rate, target delta
- Churn percentage by contract type, tenure band, internet service and payment method
- Customer 360 details and a CSV export button

Take screenshots including **the scorecard and all four charts**. To stop the server, click CMD and press `Ctrl+C`.

### Step 7 — Complete submission

Submit `PROJECT_REPORT.md`, `sql\schema.sql`, `sql\analysis_queries.sql`, `etl.py`, `verify.py`, `dashboard.py`, `telecom_churn.db`, the `outputs\` CSVs/log, and screenshots. Add 2–3 segment-specific retention recommendations based on the results. There is a checklist in `PROJECT_REPORT.md`.

## Project structure

```text
telecom_customer_360_churn_project/
├── README.md                      ← this guide
├── PROJECT_REPORT.md              ← mapping, DDL explanation, ETL rationale
├── requirements.txt
├── etl.py                         ← dataset download, cleaning, 3NF, mart
├── verify.py                      ← row counts, FK checks, churn results
├── dashboard.py                   ← Streamlit churn reporting
├── sql/
│   ├── schema.sql                 ← full DDL (raw, clean, 3NF, star, view)
│   └── analysis_queries.sql       ← evidence + breakdown queries
├── data/
│   └── Telco-Customer-Churn.csv   ← downloaded at first ETL run
├── outputs/
│   ├── summary.csv                ← created by ETL
│   ├── churn_by_*.csv             ← created by ETL
│   └── etl_run_log.txt            ← created by ETL
└── telecom_churn.db               ← created by ETL
```

## Architecture and grain

`IBM CSV → raw_telco → stg_telco_clean → 3NF Customer/Contract/Service/Billing → independent dim_customer/dim_contract/dim_service + fact_customer_month → v_churn_360 → Streamlit`.

The fact grain is **one customer per loaded snapshot**. This public sample is a single snapshot, **not monthly history**; the `snapshot_month` field means the ETL processing month, not the date when churn occurred. Do not claim to have computed a churn trend over time. The dashboard uses descriptive grouping, not a predictive ML model.

## Troubleshooting

| Problem | Fix |
|---|---|
| `'py' is not recognized` | Install Python Launcher, reopen CMD, or use `python` instead of `py` everywhere. |
| `No module named streamlit` | Run `py -m pip install -r requirements.txt` again in the same Python environment. |
| `CSV not found` / download error | Save the verified IBM CSV manually under `data\Telco-Customer-Churn.csv`. |
| `no such table: v_churn_360` | Rerun `py etl.py` and check that it says `SUCCESS`. |
| `Port 8501 already in use` | Run `py -m streamlit run dashboard.py --server.port 8502`. |
| Table counts are not 7,043 | Check that your CSV is the specified IBM sample (not the different IBM expanded churn version). |

**Note:** Each `py etl.py` run **recreates** this demo SQLite database. It is not an incremental production warehouse. Save copies of results before rerunning if you have modified the database.
