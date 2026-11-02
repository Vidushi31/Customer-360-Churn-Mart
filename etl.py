"""Run an independent Customer 360 telecom mart with reproducible ETL.

Windows CMD: py etl.py
Optionally:  py etl.py --csv data\\Telco-Customer-Churn.csv --snapshot-month 2026-11
"""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "telecom_churn.db"
DEFAULT_CSV = ROOT / "data" / "Telco-Customer-Churn.csv"
IBM_CSV_URL = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
    "master/data/Telco-Customer-Churn.csv"
)

COL_MAP = {
    "customerID": "customer_id", "gender": "gender", "SeniorCitizen": "senior_citizen",
    "Partner": "partner", "Dependents": "dependents", "tenure": "tenure_months",
    "PhoneService": "phone_service", "MultipleLines": "multiple_lines",
    "InternetService": "internet_service", "OnlineSecurity": "online_security",
    "OnlineBackup": "online_backup", "DeviceProtection": "device_protection",
    "TechSupport": "tech_support", "StreamingTV": "streaming_tv",
    "StreamingMovies": "streaming_movies", "Contract": "contract_type",
    "PaperlessBilling": "paperless_billing", "PaymentMethod": "payment_method",
    "MonthlyCharges": "monthly_charges", "TotalCharges": "total_charges", "Churn": "churn"
}
SERVICE_FLAGS = [
    "phone_service", "multiple_lines", "online_security", "online_backup",
    "device_protection", "tech_support", "streaming_tv", "streaming_movies"
]
SERVICE_COLUMNS = [
    "phone_service", "multiple_lines", "internet_service", "online_security",
    "online_backup", "device_protection", "tech_support", "streaming_tv", "streaming_movies"
]


def load_source(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        if csv_path != DEFAULT_CSV:
            raise FileNotFoundError(f"Custom dataset not found: {csv_path}")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        print("CSV not found. Downloading IBM's public dataset...")
        try:
            urllib.request.urlretrieve(IBM_CSV_URL, csv_path)
        except Exception as exc:
            raise RuntimeError(
                "Could not download dataset. Download manually from:\n"
                f"{IBM_CSV_URL}\n"
                f"Save it as: {DEFAULT_CSV}\n"
                "Then run: py etl.py"
            ) from exc
    raw = pd.read_csv(csv_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = sorted(set(COL_MAP) - set(raw.columns))
    if missing:
        raise ValueError(f"CSV is missing these required columns: {missing}")
    raw = raw[list(COL_MAP)].rename(columns=COL_MAP)
    if raw.empty:
        raise ValueError("CSV is empty")
    raw = raw.apply(lambda col: col.str.strip())
    if raw.customer_id.eq("").any() or raw.customer_id.duplicated().any():
        raise ValueError("Blank/duplicate customer IDs in dataset")
    return raw


def yes_no(series: pd.Series, name: str) -> pd.Series:
    normalized = series.str.strip().str.casefold().replace({
        "no internet service": "no", "no phone service": "no"
    })
    result = normalized.map({"yes": 1, "no": 0})
    if result.isna().any():
        raise ValueError(f"Unexpected Yes/No value(s) in {name}: {series[result.isna()].unique()}")
    return result.astype(int)


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    df = raw.copy()
    df["gender"] = df["gender"].str.title()
    if not df["gender"].isin(["Male", "Female"]).all():
        raise ValueError("Unexpected gender label")
    df["senior_citizen"] = pd.to_numeric(df["senior_citizen"], errors="raise").astype(int)
    if not df["senior_citizen"].isin([0, 1]).all():
        raise ValueError("SeniorCitizen must be 0 or 1")
    for col in SERVICE_FLAGS + ["partner", "dependents", "paperless_billing", "churn"]:
        df[col] = yes_no(df[col], col)
    df = df.rename(columns={"churn": "churn_flag"})

    df["internet_service"] = df["internet_service"].str.casefold().map({
        "no": "No", "dsl": "DSL", "fiber optic": "Fiber optic"
    })
    if df["internet_service"].isna().any():
        raise ValueError("Unexpected internet service value")
    df["contract_type"] = df["contract_type"].str.casefold().map({
        "month-to-month": "Month-to-month", "one year": "One year", "two year": "Two year"
    })
    if df["contract_type"].isna().any():
        raise ValueError("Unexpected contract type")
    df["payment_method"] = df["payment_method"].str.casefold().map({
        "electronic check": "Electronic check", "mailed check": "Mailed check",
        "bank transfer (automatic)": "Bank transfer (automatic)",
        "credit card (automatic)": "Credit card (automatic)"
    })
    if df["payment_method"].isna().any():
        raise ValueError("Unexpected payment method")

    df["tenure_months"] = pd.to_numeric(df["tenure_months"], errors="raise")
    if df["tenure_months"].isna().any() or (df["tenure_months"] < 0).any() or (df["tenure_months"] % 1 != 0).any():
        raise ValueError("Tenure must be nonnegative, whole months")
    df["tenure_months"] = df["tenure_months"].astype(int)
    df["tenure_band"] = pd.cut(
        df["tenure_months"], bins=[-1, 12, 24, 48, float("inf")],
        labels=["0-12 months", "13-24 months", "25-48 months", "49+ months"]
    ).astype(str)

    df["monthly_charges"] = pd.to_numeric(df["monthly_charges"], errors="coerce")
    df["total_charges"] = pd.to_numeric(df["total_charges"].replace("", None), errors="coerce")
    blank_total = int(df["total_charges"].isna().sum())
    if df.loc[df.total_charges.isna(), "tenure_months"].ne(0).any():
        raise ValueError("Blank/non-numeric TotalCharges for a customer with tenure > 0: review source")
    df["total_charges"] = df["total_charges"].fillna(0.0)
    if df["monthly_charges"].isna().any() or (df["monthly_charges"] < 0).any() or (df["total_charges"] < 0).any():
        raise ValueError("Missing/negative money value after cleaning")

    # Count phone, multiple-lines, internet, and 6 add-on services (0..9).
    df["total_services"] = (
        df[SERVICE_FLAGS].sum(axis=1)
        + df["internet_service"].ne("No").astype(int)
    ).astype(int)

    # Preserve expected table column sequence for pandas -> SQLite.
    clean_cols = [
        "customer_id", "gender", "senior_citizen", "partner", "dependents",
        "tenure_months", "tenure_band", *SERVICE_COLUMNS, "total_services",
        "contract_type", "paperless_billing", "payment_method",
        "monthly_charges", "total_charges", "churn_flag"
    ]
    return df[clean_cols], blank_total


def load_sqlite(raw: pd.DataFrame, clean: pd.DataFrame, snapshot_month: str) -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()  # Rebuild this self-contained sample from scratch on each run.
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript((ROOT / "sql" / "schema.sql").read_text(encoding="utf-8"))
        raw.to_sql("raw_telco", conn, if_exists="append", index=False)
        clean.to_sql("stg_telco_clean", conn, if_exists="append", index=False)

        customer_cols = ["customer_id", "gender", "senior_citizen", "partner", "dependents", "churn_flag"]
        clean[customer_cols].to_sql("customer_3nf", conn, if_exists="append", index=False)
        clean[["customer_id", "contract_type", "tenure_months"]].to_sql("contract_3nf", conn, if_exists="append", index=False)
        clean[["customer_id", *SERVICE_COLUMNS]].to_sql("service_3nf", conn, if_exists="append", index=False)
        clean[["customer_id", "paperless_billing", "payment_method", "monthly_charges", "total_charges"]].to_sql(
            "billing_3nf", conn, if_exists="append", index=False
        )
        clean[["customer_id", "gender", "senior_citizen", "partner", "dependents"]].to_sql(
            "dim_customer", conn, if_exists="append", index=False
        )
        clean[["contract_type"]].drop_duplicates().to_sql(
            "dim_contract", conn, if_exists="append", index=False
        )
        clean[[*SERVICE_COLUMNS, "total_services"]].drop_duplicates(subset=SERVICE_COLUMNS).to_sql(
            "dim_service", conn, if_exists="append", index=False
        )

        match_service = " AND ".join(f"s.{c} = p.{c}" for c in SERVICE_COLUMNS)
        fact_sql = f"""
            INSERT INTO fact_customer_month
                (customer_key, contract_key, service_key, snapshot_month,
                 tenure_months, tenure_band, payment_method, paperless_billing,
                 monthly_charges, total_charges, churn_flag)
            SELECT dc.customer_key, dct.contract_key, s.service_key, ?,
                   co.tenure_months, cl.tenure_band, b.payment_method,
                   b.paperless_billing, b.monthly_charges, b.total_charges,
                   c.churn_flag
            FROM customer_3nf c
            JOIN contract_3nf co ON co.customer_id = c.customer_id
            JOIN service_3nf p ON p.customer_id = c.customer_id
            JOIN billing_3nf b ON b.customer_id = c.customer_id
            JOIN stg_telco_clean cl ON cl.customer_id = c.customer_id
            JOIN dim_customer dc ON dc.customer_id = c.customer_id
            JOIN dim_contract dct ON dct.contract_type = co.contract_type
            JOIN dim_service s ON {match_service}
        """
        conn.execute(fact_sql, (snapshot_month,))
        conn.commit()
        fact_rows = conn.execute("SELECT COUNT(*) FROM fact_customer_month").fetchone()[0]
        if fact_rows != len(clean):
            raise RuntimeError(f"Fact load mismatch: {fact_rows} vs {len(clean)} source rows")
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise RuntimeError(f"Foreign-key violations: {fk_errors[:5]}")


def write_outputs(blank_total: int, snapshot_month: str, source_path: Path) -> None:
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM v_churn_360", conn)
        summary = pd.DataFrame([{
            "customers": len(df), "churned_customers": int(df.churn_flag.sum()),
            "overall_churn_pct": round(float(df.churn_flag.mean() * 100), 2),
            "zero_tenure_blank_total_charges_cleaned": blank_total,
            "import_snapshot_month_not_historical_month": snapshot_month
        }])
        summary.to_csv(out / "summary.csv", index=False)
        for col in ["contract_type", "tenure_band", "internet_service", "payment_method"]:
            grouped = df.groupby(col, dropna=False).agg(
                customers=("customer_id", "count"), churned=("churn_flag", "sum")
            ).reset_index()
            grouped["churn_rate_pct"] = (100 * grouped["churned"] / grouped["customers"]).round(2)
            grouped.to_csv(out / f"churn_by_{col}.csv", index=False)
        churn = float(df.churn_flag.mean() * 100)
        (out / "etl_run_log.txt").write_text(
            f"Data source file: {source_path}\n"
            f"Canonical IBM dataset: {IBM_CSV_URL}\n"
            f"Rows loaded (raw, cleaned, fact): {len(df)} / {len(df)} / {len(df)}\n"
            f"Missing TotalCharges repaired for tenure=0: {blank_total}\n"
            f"Churned: {df.churn_flag.sum()}\nOverall churn: {churn:.2f}%\n"
            f"Load month label: {snapshot_month} (NOT an observed historical month)\n",
            encoding="utf-8"
        )
    print("\nSUCCESS: ETL finished")
    print((out / "etl_run_log.txt").read_text(encoding="utf-8"))
    print("Database:", DB_PATH)
    print("Exports:", out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build raw, cleaned, 3NF, star-schema churn mart")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Optional source CSV path")
    parser.add_argument("--snapshot-month", default=dt.date.today().strftime("%Y-%m"), help="ETL load month YYYY-MM; not the dataset's event month")
    args = parser.parse_args()
    try:
        dt.datetime.strptime(args.snapshot_month, "%Y-%m")
    except ValueError as exc:
        raise SystemExit("Use --snapshot-month YYYY-MM, e.g. 2026-11") from exc
    raw = load_source(args.csv.resolve())
    clean, blank_total = clean_data(raw)
    load_sqlite(raw, clean, args.snapshot_month)
    write_outputs(blank_total, args.snapshot_month, args.csv.resolve())


if __name__ == "__main__":
    main()
