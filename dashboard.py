"""Interactive Customer 360 churn dashboard. Start: py -m streamlit run dashboard.py"""
from pathlib import Path
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB = ROOT / "telecom_churn.db"
st.set_page_config(page_title="Customer 360 | Telecom Churn", page_icon="📡", layout="wide")

st.title("📡 Customer 360 & Churn Mart")
st.caption("IBM Telco sample • independent SQLite data mart • one imported customer snapshot")

if not DB.exists():
    st.error("The database is missing. First open CMD in this folder and run: py etl.py")
    st.stop()


@st.cache_data(show_spinner=False)
def read_mart(db_mtime: float) -> pd.DataFrame:
    with sqlite3.connect(DB) as conn:
        return pd.read_sql_query("SELECT * FROM v_churn_360", conn)


df = read_mart(DB.stat().st_mtime)
if df.empty:
    st.error("The mart is empty. Run the ETL again.")
    st.stop()

st.sidebar.header("Dashboard filters")
target = st.sidebar.slider("Churn target (%)", min_value=5, max_value=40, value=20, step=1)

filter_specs = [
    ("Contract", "contract_type"),
    ("Tenure band", "tenure_band"),
    ("Internet service", "internet_service"),
    ("Payment method", "payment_method"),
]
selected = {}
for title, column in filter_specs:
    all_options = sorted(df[column].dropna().unique().tolist())
    selected[column] = st.sidebar.multiselect(title, all_options, default=all_options)

view = df.copy()
for col, values in selected.items():
    view = view[view[col].isin(values)]

if view.empty:
    st.warning("No records match these filters. Select at least one option per filter.")
    st.stop()

customers = len(view)
churned = int(view.churn_flag.sum())
rate = churned / customers * 100
m1, m2, m3, m4 = st.columns(4)
m1.metric("Customers", f"{customers:,}")
m2.metric("Churned customers", f"{churned:,}")
m3.metric("Churn rate", f"{rate:.2f}%")
m4.metric("Vs. target (percentage points)", f"{rate - target:+.2f}", delta=f"{rate-target:+.2f} pp", delta_color="inverse")
if rate <= target:
    st.success(f"Churn is at or below the illustrative target ({target}%).")
else:
    st.warning(f"Churn is {rate-target:.2f} percentage points above the illustrative {target}% target.")


def chart_for(column: str, title: str, ordered_labels: list[str] | None = None):
    agg = view.groupby(column, as_index=False).agg(
        customers=("customer_id", "size"), churned=("churn_flag", "sum")
    )
    agg["churn_rate"] = 100 * agg["churned"] / agg["customers"]
    if ordered_labels:
        agg[column] = pd.Categorical(agg[column], categories=ordered_labels, ordered=True)
        agg = agg.sort_values(column)
    else:
        agg = agg.sort_values("churn_rate", ascending=False)
    fig = px.bar(
        agg, x=column, y="churn_rate", color="churn_rate",
        color_continuous_scale="Blues", text="churn_rate",
        hover_data={"customers": True, "churned": True, "churn_rate": ":.2f"},
        labels={"churn_rate": "Churn rate (%)", column: ""}, title=title
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.add_hline(y=target, line_dash="dash", line_color="orange", annotation_text=f"Target: {target}%")
    fig.update_layout(showlegend=False, coloraxis_showscale=False, yaxis_range=[0, max(10, float(agg.churn_rate.max()) * 1.28, target * 1.2)], margin=dict(t=55,b=15))
    return fig

c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(chart_for("contract_type", "Churn by contract"), use_container_width=True)
with c2:
    st.plotly_chart(chart_for("tenure_band", "Churn by tenure band", ["0-12 months", "13-24 months", "25-48 months", "49+ months"]), use_container_width=True)
c3, c4 = st.columns(2)
with c3:
    st.plotly_chart(chart_for("internet_service", "Churn by internet service"), use_container_width=True)
with c4:
    st.plotly_chart(chart_for("payment_method", "Churn by payment method"), use_container_width=True)

st.subheader("Customer 360 detail")
st.dataframe(
    view[["customer_id", "contract_type", "tenure_band", "internet_service",
          "payment_method", "total_services", "monthly_charges", "churn_flag"]],
    use_container_width=True, hide_index=True
)
st.download_button(
    "Export filtered Customer 360 CSV",
    data=view.to_csv(index=False).encode("utf-8"),
    file_name="filtered_customer_360.csv", mime="text/csv"
)
st.caption(
    "Method: churn % = customers marked Churn=Yes ÷ customers in segment × 100. "
    "The target is a user-selected example, not an IBM benchmark. "
    "The sample has one snapshot, not actual monthly history; its load-month label must not be used as a churn trend. "
    "Associations here do not demonstrate causes."
)
