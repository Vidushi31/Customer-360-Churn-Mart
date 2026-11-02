"""Check row parity, keys, and complete churn mart; print SQL evidence."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "telecom_churn.db"
if not DB.exists():
    raise SystemExit("Database not found. Run: py etl.py")

with sqlite3.connect(DB) as conn:
    conn.execute("PRAGMA foreign_keys = ON")
    names = [
        "raw_telco", "stg_telco_clean", "customer_3nf", "contract_3nf",
        "service_3nf", "billing_3nf", "dim_customer", "dim_contract",
        "dim_service", "fact_customer_month", "v_churn_360"
    ]
    counts = {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in names}
    print("TABLE / VIEW                    ROWS")
    print("-" * 40)
    for name, n in counts.items():
        print(f"{name:<31} {n:>6}")
    expected = counts["raw_telco"]
    for name in ["stg_telco_clean", "customer_3nf", "contract_3nf", "service_3nf",
                 "billing_3nf", "dim_customer", "fact_customer_month", "v_churn_360"]:
        assert counts[name] == expected, f"Row mismatch for {name}"
    assert len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0
    assert conn.execute("SELECT COUNT(*) FROM fact_customer_month WHERE churn_flag NOT IN (0,1)").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM v_churn_360 WHERE total_services NOT BETWEEN 0 AND 9").fetchone()[0] == 0
    total, churned, churn_pct = conn.execute(
        "SELECT COUNT(*), SUM(churn_flag), ROUND(100.0 * AVG(churn_flag),2) FROM fact_customer_month"
    ).fetchone()
    print("\nOVERALL CHURN")
    print(f"Customers={total}  Churned={churned}  ChurnRate={churn_pct}%")
    print("\nCHURN BY CONTRACT")
    for row in conn.execute("""
        SELECT contract_type, COUNT(*), SUM(churn_flag), ROUND(AVG(churn_flag)*100, 2)
        FROM v_churn_360 GROUP BY contract_type ORDER BY 4 DESC
    """):
        print(row)
    print("\nALL CHECKS PASSED")
