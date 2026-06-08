WITH staged AS (
    SELECT * FROM {{ ref('stg_trades_raw') }}
),
max_versions AS (
    SELECT
        trade_id,
        MAX(version) AS max_version
    FROM staged
    GROUP BY trade_id
),
trades_with_version_context AS (
    SELECT
        s.*,
        mv.max_version
    FROM staged s
    LEFT JOIN max_versions mv ON s.trade_id = mv.trade_id
),
validated AS (
    SELECT
        trade_id,
        version,
        trade_date,
        maturity_date,
        counterparty,
        notional,
        currency,
        trade_type,
        status,
        ingested_at,
        dbt_updated_at,
        max_version,
        CASE
            -- Rule 1: Reject lower version (stale amendment)
            WHEN version < max_version THEN 'REJECTED'
            -- Rule 2: Reject invalid notional
            WHEN notional <= 0 THEN 'REJECTED'
            -- Rule 3: Reject trades maturing within 30 days (won't survive settlement window)
            WHEN maturity_date >= CURRENT_DATE()
                AND maturity_date <= DATEADD(day, 30, CURRENT_DATE())
                AND version = max_version
                THEN 'REJECTED'
            -- Rule 4: Mark as expired if maturity already passed
            WHEN maturity_date < CURRENT_DATE() AND version = max_version THEN 'EXPIRED'
            -- Rule 5: Valid active trade
            WHEN version = max_version THEN 'ACTIVE'
            ELSE 'ACTIVE'
        END AS derived_status,
        CASE
            WHEN version < max_version
                THEN 'RULE_1: Lower version ' || version::VARCHAR || ' rejected - max version is ' || max_version::VARCHAR
            WHEN notional <= 0
                THEN 'RULE_5: Zero or negative notional - ' || notional::VARCHAR
            WHEN maturity_date < CURRENT_DATE()
                AND maturity_date >= DATEADD(day, -30, CURRENT_DATE())
                AND version = max_version
                THEN 'RULE_3: Maturity date ' || maturity_date::VARCHAR || ' is earlier than today'
            ELSE NULL
        END AS rejection_reason
    FROM trades_with_version_context
)
SELECT * FROM validated
