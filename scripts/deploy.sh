#!/bin/bash
# Full deploy: terraform (ECR repos) → build docker → terraform (lambdas) → webhook + dashboard
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Step 1: Terraform apply (creates ECR repos + all infra) ==="
cd "$PROJECT_DIR/infrastructure"
terraform init -input=false
terraform apply -auto-approve

echo ""
echo "=== Step 2: Build & push Docker images ==="
bash "$SCRIPT_DIR/build.sh"

echo ""
echo "=== Step 3: Update Lambda functions to use new images ==="
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-east-1"
ECR_BASE="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

aws lambda update-function-code --function-name stock-intel-bot-handler \
  --image-uri "$ECR_BASE/stock-intel-bot:latest" --no-cli-pager
aws lambda update-function-code --function-name stock-intel-scanner \
  --image-uri "$ECR_BASE/stock-intel-scanner:latest" --no-cli-pager
aws lambda update-function-code --function-name stock-intel-alert-sender \
  --image-uri "$ECR_BASE/stock-intel-alert-sender:latest" --no-cli-pager

echo ""
echo "=== Step 4: Set Telegram webhook ==="
WEBHOOK_URL=$(terraform output -raw telegram_webhook_url)
BOT_TOKEN=$(grep telegram_bot_token terraform.tfvars | cut -d'"' -f2)
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}" | python3 -m json.tool

echo ""
echo "=== Step 5: Upload dashboard ==="
DASHBOARD_BUCKET=$(terraform output -raw s3_dashboard_url | sed 's|http://||' | sed 's|\.s3-website.*||')
aws s3 sync "$PROJECT_DIR/src/dashboard/" "s3://${DASHBOARD_BUCKET}/" --exclude "*.DS_Store"

echo ""
echo "=== Deploy complete ==="
terraform output
echo ""
echo "Send /help to your Telegram bot to test!"
