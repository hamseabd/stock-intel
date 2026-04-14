terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  lambda_runtime = "python3.12"
  lambda_arch    = "arm64" # Graviton — 20% cheaper
  tags = {
    Project = var.project_name
  }
}

# ── IAM Role for all Lambdas ──────────────────────────────────────────────

resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
        ]
        Resource = [
          aws_dynamodb_table.portfolio.arn,
          "${aws_dynamodb_table.portfolio.arn}/index/*",
          aws_dynamodb_table.watchlist.arn,
          aws_dynamodb_table.alerts.arn,
          "${aws_dynamodb_table.alerts.arn}/index/*",
          aws_dynamodb_table.congress_trades.arn,
          "${aws_dynamodb_table.congress_trades.arn}/index/*",
          aws_dynamodb_table.trades.arn,
          "${aws_dynamodb_table.trades.arn}/index/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*",
          aws_s3_bucket.dashboard.arn,
          "${aws_s3_bucket.dashboard.arn}/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = [aws_sqs_queue.alerts.arn]
      },
    ]
  })
}

# ── DynamoDB Tables ────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "portfolio" {
  name         = "${var.project_name}-portfolio"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "chat_id"
  range_key    = "position_id"

  attribute {
    name = "chat_id"
    type = "S"
  }
  attribute {
    name = "position_id"
    type = "S"
  }
  point_in_time_recovery {
    enabled = true
  }
  tags = local.tags
}

resource "aws_dynamodb_table" "watchlist" {
  name         = "${var.project_name}-watchlist"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "chat_id"
  range_key    = "ticker"

  attribute {
    name = "chat_id"
    type = "S"
  }
  attribute {
    name = "ticker"
    type = "S"
  }
  point_in_time_recovery {
    enabled = true
  }
  tags = local.tags
}

resource "aws_dynamodb_table" "alerts" {
  name         = "${var.project_name}-alerts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "chat_id"
  range_key    = "sk"

  attribute {
    name = "chat_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  point_in_time_recovery {
    enabled = true
  }
  tags = local.tags
}

resource "aws_dynamodb_table" "congress_trades" {
  name         = "${var.project_name}-congress-trades"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "ticker"
    type = "S"
  }
  attribute {
    name = "trade_date"
    type = "S"
  }

  global_secondary_index {
    name            = "ticker-trade_date-index"
    hash_key        = "ticker"
    range_key       = "trade_date"
    projection_type = "ALL"
  }
  point_in_time_recovery {
    enabled = true
  }
  tags = local.tags
}

resource "aws_dynamodb_table" "trades" {
  name         = "${var.project_name}-trades"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "chat_id"
  range_key    = "timestamp"

  attribute {
    name = "chat_id"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }
  point_in_time_recovery {
    enabled = true
  }
  tags = local.tags
}

# ── S3 Buckets ─────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "data" {
  bucket = "${var.project_name}-data-${data.aws_caller_identity.current.account_id}"
  tags   = local.tags
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket" "dashboard" {
  bucket = "${var.project_name}-dashboard-${data.aws_caller_identity.current.account_id}"
  tags   = local.tags
}

resource "aws_s3_bucket_website_configuration" "dashboard" {
  bucket = aws_s3_bucket.dashboard.id
  index_document { suffix = "index.html" }
  error_document { key = "index.html" }
}

resource "aws_s3_bucket_public_access_block" "dashboard" {
  bucket                  = aws_s3_bucket.dashboard.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "dashboard" {
  bucket = aws_s3_bucket.dashboard.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicRead"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.dashboard.arn}/*"
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.dashboard]
}

data "aws_caller_identity" "current" {}

# ── SQS Alert Queue ───────────────────────────────────────────────────────

resource "aws_sqs_queue" "alerts_dlq" {
  name                      = "${var.project_name}-alerts-dlq"
  message_retention_seconds = 1209600 # 14 days
  sqs_managed_sse_enabled   = true
  tags                      = local.tags
}

resource "aws_sqs_queue" "alerts" {
  name                       = "${var.project_name}-alerts"
  message_retention_seconds  = 86400 # 1 day
  visibility_timeout_seconds = 60
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.alerts_dlq.arn
    maxReceiveCount     = 3
  })
  tags = local.tags
}

# ── ECR Repositories ───────────────────────────────────────────────────────

resource "aws_ecr_repository" "bot" {
  name                 = "${var.project_name}-bot"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  tags                 = local.tags
}

resource "aws_ecr_repository" "scanner" {
  name                 = "${var.project_name}-scanner"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  tags                 = local.tags
}

resource "aws_ecr_repository" "alert_sender" {
  name                 = "${var.project_name}-alert-sender"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  tags                 = local.tags
}

# ── Lambda Functions (Docker images) ───────────────────────────────────────

# Bot handler — Telegram webhook
resource "aws_lambda_function" "bot_handler" {
  function_name = "${var.project_name}-bot-handler"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.bot.repository_url}:latest"
  architectures = [local.lambda_arch]
  timeout       = 60
  memory_size   = 256

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN       = var.telegram_bot_token
      TELEGRAM_CHAT_ID         = var.telegram_chat_id
      ANTHROPIC_API_KEY        = var.anthropic_api_key
      DYNAMODB_TABLE_PORTFOLIO = aws_dynamodb_table.portfolio.name
      DYNAMODB_TABLE_WATCHLIST  = aws_dynamodb_table.watchlist.name
      DYNAMODB_TABLE_ALERTS    = aws_dynamodb_table.alerts.name
      DYNAMODB_TABLE_CONGRESS  = aws_dynamodb_table.congress_trades.name
      DYNAMODB_TABLE_TRADES    = aws_dynamodb_table.trades.name
      S3_BUCKET_DATA           = aws_s3_bucket.data.id
      S3_BUCKET_DASHBOARD      = aws_s3_bucket.dashboard.id
      SQS_ALERT_QUEUE_URL      = aws_sqs_queue.alerts.url
    }
  }
  tags = local.tags
}

# Scanner — scheduled scans
resource "aws_lambda_function" "scanner" {
  function_name = "${var.project_name}-scanner"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.scanner.repository_url}:latest"
  architectures = [local.lambda_arch]
  timeout       = 120
  memory_size   = 256

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN       = var.telegram_bot_token
      TELEGRAM_CHAT_ID         = var.telegram_chat_id
      DYNAMODB_TABLE_PORTFOLIO = aws_dynamodb_table.portfolio.name
      DYNAMODB_TABLE_WATCHLIST  = aws_dynamodb_table.watchlist.name
      DYNAMODB_TABLE_ALERTS    = aws_dynamodb_table.alerts.name
      DYNAMODB_TABLE_CONGRESS  = aws_dynamodb_table.congress_trades.name
      S3_BUCKET_DATA           = aws_s3_bucket.data.id
      S3_BUCKET_DASHBOARD      = aws_s3_bucket.dashboard.id
      SQS_ALERT_QUEUE_URL      = aws_sqs_queue.alerts.url
    }
  }
  tags = local.tags
}

# Alert sender — processes SQS messages and sends Telegram alerts
resource "aws_lambda_function" "alert_sender" {
  function_name = "${var.project_name}-alert-sender"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.alert_sender.repository_url}:latest"
  architectures = [local.lambda_arch]
  timeout       = 30
  memory_size   = 128

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN    = var.telegram_bot_token
      TELEGRAM_CHAT_ID      = var.telegram_chat_id
      DYNAMODB_TABLE_ALERTS = aws_dynamodb_table.alerts.name
    }
  }
  tags = local.tags
}

# SQS → Alert sender trigger
resource "aws_lambda_event_source_mapping" "alert_sqs" {
  event_source_arn = aws_sqs_queue.alerts.arn
  function_name    = aws_lambda_function.alert_sender.arn
  batch_size       = 5
}

# ── API Gateway (HTTP API — cheaper than REST) ─────────────────────────────

resource "aws_apigatewayv2_api" "telegram_webhook" {
  name          = "${var.project_name}-webhook"
  protocol_type = "HTTP"
  tags          = local.tags
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.telegram_webhook.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "bot" {
  api_id                 = aws_apigatewayv2_api.telegram_webhook.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.bot_handler.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "webhook" {
  api_id    = aws_apigatewayv2_api.telegram_webhook.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.bot.id}"
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bot_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.telegram_webhook.execution_arn}/*/*"
}

# ── EventBridge Schedules ──────────────────────────────────────────────────

# Price scanner — every 5 min during market hours (Mon-Fri 9:30-16:00 ET = 14:30-21:00 UTC)
resource "aws_cloudwatch_event_rule" "price_scanner" {
  name                = "${var.project_name}-price-scanner"
  schedule_expression = "cron(0/5 14-20 ? * MON-FRI *)"
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "price_scanner" {
  rule = aws_cloudwatch_event_rule.price_scanner.name
  arn  = aws_lambda_function.scanner.arn
  input = jsonencode({ scanner = "price" })
}

# Options flow scanner — every 30 min
resource "aws_cloudwatch_event_rule" "flow_scanner" {
  name                = "${var.project_name}-flow-scanner"
  schedule_expression = "rate(30 minutes)"
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "flow_scanner" {
  rule = aws_cloudwatch_event_rule.flow_scanner.name
  arn  = aws_lambda_function.scanner.arn
  input = jsonencode({ scanner = "flow" })
}

# Congress scanner — every 6 hours
resource "aws_cloudwatch_event_rule" "congress_scanner" {
  name                = "${var.project_name}-congress-scanner"
  schedule_expression = "rate(6 hours)"
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "congress_scanner" {
  rule = aws_cloudwatch_event_rule.congress_scanner.name
  arn  = aws_lambda_function.scanner.arn
  input = jsonencode({ scanner = "congress" })
}

# Dark pool scanner — daily at 5 PM ET (21:00 UTC)
resource "aws_cloudwatch_event_rule" "darkpool_scanner" {
  name                = "${var.project_name}-darkpool-scanner"
  schedule_expression = "cron(0 21 ? * MON-FRI *)"
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "darkpool_scanner" {
  rule = aws_cloudwatch_event_rule.darkpool_scanner.name
  arn  = aws_lambda_function.scanner.arn
  input = jsonencode({ scanner = "darkpool" })
}

# Risk scanner — every hour during market hours
resource "aws_cloudwatch_event_rule" "risk_scanner" {
  name                = "${var.project_name}-risk-scanner"
  schedule_expression = "rate(1 hour)"
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "risk_scanner" {
  rule = aws_cloudwatch_event_rule.risk_scanner.name
  arn  = aws_lambda_function.scanner.arn
  input = jsonencode({ scanner = "risk" })
}

# Technicals scanner — every hour
resource "aws_cloudwatch_event_rule" "technicals_scanner" {
  name                = "${var.project_name}-technicals-scanner"
  schedule_expression = "rate(1 hour)"
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "technicals_scanner" {
  rule = aws_cloudwatch_event_rule.technicals_scanner.name
  arn  = aws_lambda_function.scanner.arn
  input = jsonencode({ scanner = "technicals" })
}

# Earnings scanner — daily at 8 AM ET (12:00 UTC)
resource "aws_cloudwatch_event_rule" "earnings_scanner" {
  name                = "${var.project_name}-earnings-scanner"
  schedule_expression = "cron(0 12 ? * MON-FRI *)"
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "earnings_scanner" {
  rule = aws_cloudwatch_event_rule.earnings_scanner.name
  arn  = aws_lambda_function.scanner.arn
  input = jsonencode({ scanner = "earnings" })
}

# News scanner — every 30 min
resource "aws_cloudwatch_event_rule" "news_scanner" {
  name                = "${var.project_name}-news-scanner"
  schedule_expression = "rate(30 minutes)"
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "news_scanner" {
  rule = aws_cloudwatch_event_rule.news_scanner.name
  arn  = aws_lambda_function.scanner.arn
  input = jsonencode({ scanner = "news" })
}

# Lambda permissions for EventBridge
resource "aws_lambda_permission" "scanner_price" {
  statement_id  = "AllowEventBridge-price"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.price_scanner.arn
}

resource "aws_lambda_permission" "scanner_flow" {
  statement_id  = "AllowEventBridge-flow"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.flow_scanner.arn
}

resource "aws_lambda_permission" "scanner_congress" {
  statement_id  = "AllowEventBridge-congress"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.congress_scanner.arn
}

resource "aws_lambda_permission" "scanner_darkpool" {
  statement_id  = "AllowEventBridge-darkpool"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.darkpool_scanner.arn
}

resource "aws_lambda_permission" "scanner_risk" {
  statement_id  = "AllowEventBridge-risk"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.risk_scanner.arn
}

resource "aws_lambda_permission" "scanner_technicals" {
  statement_id  = "AllowEventBridge-technicals"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.technicals_scanner.arn
}

resource "aws_lambda_permission" "scanner_earnings" {
  statement_id  = "AllowEventBridge-earnings"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.earnings_scanner.arn
}

resource "aws_lambda_permission" "scanner_news" {
  statement_id  = "AllowEventBridge-news"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.news_scanner.arn
}
