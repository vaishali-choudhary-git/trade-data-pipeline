from datetime import datetime, timedelta
import os
import subprocess

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.operators.bash import BashOperator

import snowflake.connector

SNOWFLAKE_CONFIG = {
    "account":   "NWRJMLL-RS38964",
    "user":      "VAISHALICHOUDHARY10796",
    "password":  os.environ.get("SNOWFLAKE_PASSWORD"),
    "database":  "TRADE_DB",
    "schema":    "RAW",
    "warehouse": "TRADE_WH",
    "role":      "SYSADMIN"
}

PROJECT_ROOT = os.path.expanduser(
    "~/Documents/Docs/Vaishali/Documents/JobDocs/For Deutsche Bank/trade-data-pipeline"
)
DATA_GENERATOR = os.path.join(PROJECT_ROOT, "data_generator/generate_trades.py")
DBT_PROJECT    = os.path.join(PROJECT_ROOT, "dbt/trade_pipeline")

default_args = {
    "owner":            "data-engineering",
    "depends_on_past":  False,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,
    "email_on_retry":   False,
}

def generate_and_ingest(**context):
    result = subprocess.run(
        ["python3.11", DATA_GENERATOR],
        capture_output=True, text=True,
        env={**os.environ, "SNOWFLAKE_PASSWORD": os.environ.get("SNOWFLAKE_PASSWORD", "")}
    )
    print(result.stdout)
    if result.returncode != 0:
        raise Exception(f"Trade generator failed:\n{result.stderr}")

def pipeline_health_check(**context):
    conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM TRADE_DB.RAW.TRADES_RAW")
        raw_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM TRADE_DB.MART.TRADES_VALID")
        valid_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM TRADE_DB.MART.TRADES_REJECTED")
        rejected_count = cur.fetchone()[0]
        print(f"Raw: {raw_count} | Valid: {valid_count} | Rejected: {rejected_count}")
        context['ti'].xcom_push(key='trade_stats', value={
            'raw': raw_count, 'valid': valid_count, 'rejected': rejected_count
        })
    finally:
        cur.close()
        conn.close()

def write_audit_log(**context):
    import uuid, json
    stats = context['ti'].xcom_pull(key='trade_stats', task_ids='health_check')
    conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
    cur  = conn.cursor()
    try:
        run_id = str(uuid.uuid4())
        rejection_json = json.dumps({"total_rejected": stats.get('rejected', 0)})
        cur.execute("""
            INSERT INTO TRADE_DB.AUDIT.PIPELINE_AUDIT_LOG
            (RUN_ID, RUN_TIMESTAMP, TRADES_INGESTED, TRADES_VALID,
             TRADES_REJECTED, TRADES_EXPIRED, REJECTION_BREAKDOWN, PIPELINE_STATUS)
            SELECT %s, CURRENT_TIMESTAMP(), %s, %s, %s, 0, PARSE_JSON(%s), 'SUCCESS'
        """, (run_id, stats.get('raw', 0), stats.get('valid', 0),
              stats.get('rejected', 0), rejection_json))
        print(f"Audit log written - run_id: {run_id}")
    finally:
        cur.close()
        conn.close()

with DAG(
    dag_id="trade_pipeline",
    description="Deutsche Bank trade data pipeline",
    default_args=default_args,
    schedule="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["trade", "snowflake", "dbt"],
) as dag:

    ingest = PythonOperator(
        task_id="generate_and_ingest",
        python_callable=generate_and_ingest,
    )
    dbt_staging = BashOperator(
        task_id="dbt_staging",
        bash_command=f"cd '{DBT_PROJECT}' && dbt run --select staging",
    )
    dbt_intermediate = BashOperator(
        task_id="dbt_intermediate",
        bash_command=f"cd '{DBT_PROJECT}' && dbt run --select intermediate",
    )
    dbt_mart = BashOperator(
        task_id="dbt_mart",
        bash_command=f"cd '{DBT_PROJECT}' && dbt run --select mart",
    )
    dbt_tests = BashOperator(
        task_id="dbt_tests",
        bash_command=f"cd '{DBT_PROJECT}' && dbt test",
    )
    health_check = PythonOperator(
        task_id="health_check",
        python_callable=pipeline_health_check,
    )
    audit_log = PythonOperator(
        task_id="write_audit_log",
        python_callable=write_audit_log,
    )

    ingest >> dbt_staging >> dbt_intermediate >> dbt_mart >> dbt_tests >> health_check >> audit_log
