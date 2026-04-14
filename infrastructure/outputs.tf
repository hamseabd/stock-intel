output "api_gateway_url" {
  value = aws_apigatewayv2_api.telegram_webhook.api_endpoint
}

output "s3_dashboard_url" {
  value = "http://${aws_s3_bucket.dashboard.bucket}.s3-website-${var.aws_region}.amazonaws.com"
}

output "s3_data_bucket" {
  value = aws_s3_bucket.data.id
}

output "telegram_webhook_url" {
  value = "${aws_apigatewayv2_api.telegram_webhook.api_endpoint}/webhook"
}

output "ecr_bot_url" {
  value = aws_ecr_repository.bot.repository_url
}

output "ecr_scanner_url" {
  value = aws_ecr_repository.scanner.repository_url
}

output "ecr_alert_sender_url" {
  value = aws_ecr_repository.alert_sender.repository_url
}
