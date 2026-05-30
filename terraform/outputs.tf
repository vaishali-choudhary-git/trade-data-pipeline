output "snowflake_database" {
  value = snowflake_database.trade_db.name
}

output "snowflake_warehouse" {
  value = snowflake_warehouse.trade_wh.name
}

output "snowflake_schemas" {
  value = [
    snowflake_schema.raw.name,
    snowflake_schema.staging.name,
    snowflake_schema.intermediate.name,
    snowflake_schema.mart.name,
    snowflake_schema.audit.name
  ]
}

output "trade_stage_name" {
  value = snowflake_stage.trade_stage.name
}
