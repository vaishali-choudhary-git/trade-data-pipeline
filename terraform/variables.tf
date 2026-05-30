variable "snowflake_org" {
  description = "Snowflake organization name"
  type        = string
  default     = "NWRJMLL"
}

variable "snowflake_account" {
  description = "Snowflake account name"
  type        = string
  default     = "RS38964"
}

variable "snowflake_username" {
  description = "Snowflake username"
  type        = string
  default     = "VAISHALICHOUDHARY10796"
}

variable "snowflake_password" {
  description = "Snowflake password"
  type        = string
  sensitive   = true
}

variable "snowflake_warehouse" {
  description = "Snowflake warehouse name"
  type        = string
  default     = "TRADE_WH"
}

variable "snowflake_database" {
  description = "Snowflake database name"
  type        = string
  default     = "TRADE_DB"
}
