terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 1.0"
    }
  }
}

provider "snowflake" {
  account_name      = var.snowflake_account
  organization_name = var.snowflake_org
  user              = var.snowflake_username
  password          = var.snowflake_password
  role              = "SYSADMIN"
  preview_features_enabled = [
    "snowflake_table_resource",
    "snowflake_file_format_resource",
    "snowflake_stage_resource"
  ]
}

provider "snowflake" {
  alias             = "securityadmin"
  account_name      = var.snowflake_account
  organization_name = var.snowflake_org
  user              = var.snowflake_username
  password          = var.snowflake_password
  role              = "SECURITYADMIN"
}

resource "snowflake_database" "trade_db" {
  name    = var.snowflake_database
  comment = "Deutsche Bank trade data pipeline database"
}

resource "snowflake_warehouse" "trade_wh" {
  name                = var.snowflake_warehouse
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true
  comment             = "Trade pipeline warehouse - auto suspends after 60s"
}

resource "snowflake_schema" "raw" {
  database = snowflake_database.trade_db.name
  name     = "RAW"
  comment  = "Raw ingested trade data from Snowpipe"
}

resource "snowflake_schema" "staging" {
  database = snowflake_database.trade_db.name
  name     = "STAGING"
  comment  = "DBT staging layer"
}

resource "snowflake_schema" "intermediate" {
  database = snowflake_database.trade_db.name
  name     = "INTERMEDIATE"
  comment  = "DBT intermediate layer - business rules applied"
}

resource "snowflake_schema" "mart" {
  database = snowflake_database.trade_db.name
  name     = "MART"
  comment  = "DBT mart layer - final valid and rejected trades"
}

resource "snowflake_schema" "audit" {
  database = snowflake_database.trade_db.name
  name     = "AUDIT"
  comment  = "Audit logs for pipeline runs"
}

resource "snowflake_table" "trades_raw" {
  database = snowflake_database.trade_db.name
  schema   = snowflake_schema.raw.name
  name     = "TRADES_RAW"
  comment  = "Raw trades landed by Snowpipe"

  column {
    name     = "TRADE_ID"
    type     = "VARCHAR(50)"
    nullable = false
  }
  column {
    name     = "VERSION"
    type     = "NUMBER(10,0)"
    nullable = false
  }
  column {
    name = "TRADE_DATE"
    type = "DATE"
  }
  column {
    name = "MATURITY_DATE"
    type = "DATE"
  }
  column {
    name = "COUNTERPARTY"
    type = "VARCHAR(100)"
  }
  column {
    name = "NOTIONAL"
    type = "NUMBER(20,2)"
  }
  column {
    name = "CURRENCY"
    type = "VARCHAR(10)"
  }
  column {
    name = "TRADE_TYPE"
    type = "VARCHAR(50)"
  }
  column {
    name = "STATUS"
    type = "VARCHAR(20)"
  }
  column {
    name = "INGESTED_AT"
    type = "TIMESTAMP_NTZ"
  }
}

resource "snowflake_table" "trades_rejected" {
  database = snowflake_database.trade_db.name
  schema   = snowflake_schema.mart.name
  name     = "TRADES_REJECTED"
  comment  = "Trades rejected by business rules - compliance audit"

  column {
    name = "TRADE_ID"
    type = "VARCHAR(50)"
  }
  column {
    name = "VERSION"
    type = "NUMBER(10,0)"
  }
  column {
    name = "TRADE_DATE"
    type = "DATE"
  }
  column {
    name = "MATURITY_DATE"
    type = "DATE"
  }
  column {
    name = "COUNTERPARTY"
    type = "VARCHAR(100)"
  }
  column {
    name = "NOTIONAL"
    type = "NUMBER(20,2)"
  }
  column {
    name = "CURRENCY"
    type = "VARCHAR(10)"
  }
  column {
    name = "TRADE_TYPE"
    type = "VARCHAR(50)"
  }
  column {
    name = "REJECTION_REASON"
    type = "VARCHAR(200)"
  }
  column {
    name = "REJECTED_AT"
    type = "TIMESTAMP_NTZ"
  }
}

resource "snowflake_table" "pipeline_audit_log" {
  database = snowflake_database.trade_db.name
  schema   = snowflake_schema.audit.name
  name     = "PIPELINE_AUDIT_LOG"
  comment  = "Every pipeline run logged here for monitoring"

  column {
    name = "RUN_ID"
    type = "VARCHAR(100)"
  }
  column {
    name = "RUN_TIMESTAMP"
    type = "TIMESTAMP_NTZ"
  }
  column {
    name = "TRADES_INGESTED"
    type = "NUMBER(10,0)"
  }
  column {
    name = "TRADES_VALID"
    type = "NUMBER(10,0)"
  }
  column {
    name = "TRADES_REJECTED"
    type = "NUMBER(10,0)"
  }
  column {
    name = "TRADES_EXPIRED"
    type = "NUMBER(10,0)"
  }
  column {
    name = "REJECTION_BREAKDOWN"
    type = "VARIANT"
  }
  column {
    name = "PIPELINE_STATUS"
    type = "VARCHAR(20)"
  }
  column {
    name = "ERROR_MESSAGE"
    type = "VARCHAR(1000)"
  }
}

resource "snowflake_file_format" "csv_format" {
  database            = snowflake_database.trade_db.name
  schema              = snowflake_schema.raw.name
  name                = "TRADE_CSV_FORMAT"
  format_type         = "CSV"
  field_delimiter     = ","
  skip_header         = 1
  null_if             = ["NULL", "null", ""]
  empty_field_as_null = true
  comment             = "CSV format for trade data files"
}

resource "snowflake_stage" "trade_stage" {
  database    = snowflake_database.trade_db.name
  schema      = snowflake_schema.raw.name
  name        = "TRADE_STAGE"
  file_format = "FORMAT_NAME = ${snowflake_database.trade_db.name}.${snowflake_schema.raw.name}.${snowflake_file_format.csv_format.name}"
  comment     = "Internal stage for trade CSV file landing"
}

resource "snowflake_account_role" "dbt_role" {
  provider = snowflake.securityadmin
  name     = "DBT_ROLE"
  comment  = "Least privilege role for DBT transformations"
}

resource "snowflake_account_role" "airflow_role" {
  provider = snowflake.securityadmin
  name     = "AIRFLOW_ROLE"
  comment  = "Least privilege role for Airflow orchestration"
}

resource "snowflake_grant_privileges_to_account_role" "dbt_warehouse" {
  provider          = snowflake.securityadmin
  account_role_name = snowflake_account_role.dbt_role.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.trade_wh.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "dbt_database" {
  provider          = snowflake.securityadmin
  account_role_name = snowflake_account_role.dbt_role.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.trade_db.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "airflow_warehouse" {
  provider          = snowflake.securityadmin
  account_role_name = snowflake_account_role.airflow_role.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.trade_wh.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "airflow_database" {
  provider          = snowflake.securityadmin
  account_role_name = snowflake_account_role.airflow_role.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.trade_db.name
  }
}
