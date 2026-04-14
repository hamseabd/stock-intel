variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "stock-intel"
}

variable "telegram_bot_token" {
  type      = string
  sensitive = true
}

variable "telegram_chat_id" {
  type = string
}

variable "anthropic_api_key" {
  type      = string
  sensitive = true
}
