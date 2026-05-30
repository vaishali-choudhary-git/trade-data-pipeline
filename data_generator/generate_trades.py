import csv
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker
import snowflake.connector
import os

fake = Faker()

# ── CONFIG ────────────────────────────────────────────────
SNOWFLAKE_CONFIG = {
    "account": "NWRJMLL-RS38964",
    "user": "VAISHALICHOUDHARY10796",
    "password": os.environ.get("SNOWFLAKE_PASSWORD"),
    "database": "TRADE_DB",
    "schema": "RAW",
    "warehouse": "TRADE_WH",
    "role": "SYSADMIN"
}

TRADE_TYPES = ["SWAP", "FORWARD", "OPTION", "BOND", "FUTURE", "FX_SPOT"]
CURRENCIES  = ["USD", "EUR", "GBP", "JPY", "CHF", "INR", "AUD"]
OUTPUT_FILE = "trades.csv"
NUM_TRADES  = 100

# ── HELPERS ───────────────────────────────────────────────
def random_date(start_days_ago=365, end_days_ago=0):
    start = datetime.today() - timedelta(days=start_days_ago)
    end   = datetime.today() - timedelta(days=end_days_ago)
    return start + (end - start) * random.random()

def generate_trades(num_trades=NUM_TRADES):
    trades = []
    today  = datetime.today()

    # Base trade IDs - we'll reuse some to test version rules
    base_ids = [str(uuid.uuid4()) for _ in range(int(num_trades * 0.7))]

    for i in range(num_trades):
        trade_id = random.choice(base_ids)

        # Determine version - deliberately create duplicates and lower versions
        scenario = random.choices(
            ["new", "higher_version", "same_version", "lower_version"],
            weights=[50, 20, 20, 10]
        )[0]

        if scenario == "new":
            version = 1
        elif scenario == "higher_version":
            version = random.randint(2, 5)
        elif scenario == "same_version":
            version = 1
        else:  # lower_version - should be REJECTED by Rule 1
            version = 0

        # Maturity date scenarios - test Rules 3 and 4
        maturity_scenario = random.choices(
            ["future", "past_maturity", "expired_recently"],
            weights=[70, 15, 15]
        )[0]

        if maturity_scenario == "future":
            maturity_date = today + timedelta(days=random.randint(30, 1825))
        elif maturity_scenario == "past_maturity":
            # Rule 3: maturity date earlier than today - REJECT
            maturity_date = today - timedelta(days=random.randint(1, 30))
        else:
            # Rule 4: maturity date passed - mark as EXPIRED
            maturity_date = today - timedelta(days=random.randint(31, 365))

        trade_date = random_date(start_days_ago=365, end_days_ago=0)

        # Rule 5 (optional): zero notional - REJECT
        notional = 0 if random.random() < 0.05 else round(random.uniform(100000, 50000000), 2)

        trades.append({
            "trade_id":      trade_id,
            "version":       version,
            "trade_date":    trade_date.strftime("%Y-%m-%d"),
            "maturity_date": maturity_date.strftime("%Y-%m-%d"),
            "counterparty":  fake.company().replace(",", "").replace('"', ''),  
            "notional":      notional,
            "currency":      random.choice(CURRENCIES),
            "trade_type":    random.choice(TRADE_TYPES),
            "status":        "ACTIVE",
            "ingested_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    return trades

def save_to_csv(trades, filename=OUTPUT_FILE):
    fieldnames = [
        "trade_id", "version", "trade_date", "maturity_date",
        "counterparty", "notional", "currency", "trade_type",
        "status", "ingested_at"
    ]
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(trades)
    print(f"✅ Generated {len(trades)} trades → {filename}")

def upload_to_snowflake(filename=OUTPUT_FILE):
    print("🔄 Connecting to Snowflake...")
    conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
    cursor = conn.cursor()

    try:
        # Use the correct database and schema
        cursor.execute("USE DATABASE TRADE_DB")
        cursor.execute("USE SCHEMA RAW")
        cursor.execute("USE WAREHOUSE TRADE_WH")

        # Upload file to internal stage
        print(f"🔄 Uploading {filename} to Snowflake stage...")
        cursor.execute(f"PUT 'file://{os.path.abspath(filename)}' @TRADE_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE")
        print("✅ File uploaded to stage successfully")

        # Load into RAW table using COPY INTO
        print("🔄 Loading data into TRADES_RAW table...")
        cursor.execute(f"""
            COPY INTO TRADES_RAW (
                TRADE_ID, VERSION, TRADE_DATE, MATURITY_DATE,
                COUNTERPARTY, NOTIONAL, CURRENCY, TRADE_TYPE,
                STATUS, INGESTED_AT
            )
            FROM @TRADE_STAGE/{filename}.gz
            FILE_FORMAT = (FORMAT_NAME = 'TRADE_CSV_FORMAT')
            ON_ERROR = 'CONTINUE'
        """)

        # Show results
        results = cursor.fetchall()
        print(f"✅ COPY INTO complete: {results}")

        # Quick count check
        cursor.execute("SELECT COUNT(*) FROM TRADES_RAW")
        count = cursor.fetchone()[0]
        print(f"✅ Total records in TRADES_RAW: {count}")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
        print("✅ Snowflake connection closed")

if __name__ == "__main__":
    print("🚀 Starting trade data generation...")
    trades = generate_trades(NUM_TRADES)
    save_to_csv(trades)
    upload_to_snowflake()
    print("🎉 Trade generation and ingestion complete!")
