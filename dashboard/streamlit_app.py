import streamlit as st
import snowflake.connector
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="Trade Pipeline Dashboard", page_icon="📊", layout="wide")
st.title("📊 Deutsche Bank — Trade Pipeline Dashboard")
st.markdown("Real-time view of trade data processed by the pipeline")

@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        account="NWRJMLL-RS38964",
        user="VAISHALICHOUDHARY10796",
        password=os.environ.get("SNOWFLAKE_PASSWORD"),
        database="TRADE_DB",
        warehouse="TRADE_WH",
        role="SYSADMIN"
    )

@st.cache_data(ttl=60)
def run_query(sql):
    conn = get_connection()
    return pd.read_sql(sql, conn)

st.subheader("Pipeline Summary")
col1, col2, col3, col4 = st.columns(4)
raw_df      = run_query("SELECT COUNT(*) AS CNT FROM TRADE_DB.RAW.TRADES_RAW")
valid_df    = run_query("SELECT COUNT(*) AS CNT FROM TRADE_DB.MART.TRADES_VALID")
rejected_df = run_query("SELECT COUNT(*) AS CNT FROM TRADE_DB.MART.TRADES_REJECTED")
expired_df  = run_query("SELECT COUNT(*) AS CNT FROM TRADE_DB.MART.TRADES_VALID WHERE STATUS = 'EXPIRED'")
col1.metric("Total Ingested",  int(raw_df['CNT'][0]))
col2.metric("Valid Trades",    int(valid_df['CNT'][0]))
col3.metric("Rejected Trades", int(rejected_df['CNT'][0]))
col4.metric("Expired Trades",  int(expired_df['CNT'][0]))

st.divider()
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Trade Status Breakdown")
    status_df = run_query("""
        SELECT STATUS, COUNT(*) AS COUNT
        FROM TRADE_DB.MART.TRADES_VALID
        GROUP BY STATUS
        UNION ALL
        SELECT 'REJECTED', COUNT(*)
        FROM TRADE_DB.MART.TRADES_REJECTED
    """)
    fig = px.pie(status_df, values='COUNT', names='STATUS', hole=0.4,
        color_discrete_map={'ACTIVE':'#1D9E75','EXPIRED':'#BA7517','REJECTED':'#993C1D'})
    fig.update_layout(margin=dict(t=0,b=0,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Rejection Reasons")
    reasons_df = run_query("""
        SELECT SPLIT_PART(REJECTION_REASON, ':', 1) AS RULE, COUNT(*) AS COUNT
        FROM TRADE_DB.MART.TRADES_REJECTED
        GROUP BY 1 ORDER BY COUNT DESC
    """)
    fig2 = px.bar(reasons_df, x='COUNT', y='RULE', orientation='h',
        color='COUNT', color_continuous_scale='Reds')
    fig2.update_layout(margin=dict(t=0,b=0,l=0,r=0), yaxis_title="",
        xaxis_title="Count", coloraxis_showscale=False)
    st.plotly_chart(fig2, use_container_width=True)

st.divider()
st.subheader("Valid Trades")
trades_df = run_query("""
    SELECT TRADE_ID, VERSION, TRADE_DATE, MATURITY_DATE,
           COUNTERPARTY, NOTIONAL, CURRENCY, TRADE_TYPE, STATUS
    FROM TRADE_DB.MART.TRADES_VALID
    ORDER BY TRADE_DATE DESC LIMIT 50
""")
st.dataframe(trades_df, use_container_width=True)

st.divider()
st.subheader("Pipeline Audit Log")
audit_df = run_query("""
    SELECT RUN_ID, RUN_TIMESTAMP, TRADES_INGESTED,
           TRADES_VALID, TRADES_REJECTED, PIPELINE_STATUS
    FROM TRADE_DB.AUDIT.PIPELINE_AUDIT_LOG
    ORDER BY RUN_TIMESTAMP DESC LIMIT 20
""")
if audit_df.empty:
    st.info("No audit log entries yet — trigger the Airflow DAG to populate.")
else:
    st.dataframe(audit_df, use_container_width=True)

st.caption("Refreshes every 60s · Streamlit + Snowflake + DBT")
