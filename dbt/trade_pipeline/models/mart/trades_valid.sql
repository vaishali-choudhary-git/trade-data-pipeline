WITH validated AS (
    SELECT * FROM {{ ref('int_trades_validated') }}
)
SELECT
    trade_id,
    version,
    trade_date,
    maturity_date,
    counterparty,
    notional,
    currency,
    trade_type,
    derived_status   AS status,
    ingested_at,
    dbt_updated_at
FROM validated
WHERE derived_status IN ('ACTIVE', 'EXPIRED')