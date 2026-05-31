WITH source AS (
    SELECT * FROM {{ source('raw', 'TRADES_RAW') }}
),
cleaned AS (
    SELECT
        TRIM(TRADE_ID)                          AS trade_id,
        VERSION::NUMBER                         AS version,
        TRADE_DATE::DATE                        AS trade_date,
        MATURITY_DATE::DATE                     AS maturity_date,
        TRIM(UPPER(COUNTERPARTY))               AS counterparty,
        NOTIONAL::NUMBER(20,2)                  AS notional,
        TRIM(UPPER(CURRENCY))                   AS currency,
        TRIM(UPPER(TRADE_TYPE))                 AS trade_type,
        TRIM(UPPER(STATUS))                     AS status,
        INGESTED_AT::TIMESTAMP_NTZ              AS ingested_at,
        CURRENT_TIMESTAMP()                     AS dbt_updated_at
    FROM source
    WHERE TRADE_ID IS NOT NULL
      AND VERSION  IS NOT NULL
)
SELECT * FROM cleaned-- v1.1 | added pipeline version tag
