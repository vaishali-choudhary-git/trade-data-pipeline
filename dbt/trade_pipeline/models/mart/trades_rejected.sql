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
    rejection_reason,
    ingested_at,
    CURRENT_TIMESTAMP() AS rejected_at
FROM validated
WHERE derived_status = 'REJECTED'