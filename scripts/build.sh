#!/bin/bash
# Build and push Docker images to ECR
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$PROJECT_DIR/src"
INFRA_DIR="$PROJECT_DIR/infrastructure"

REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "=== Building Docker images for Lambda ==="
echo "Account: $ACCOUNT_ID | Region: $REGION"

# Login to ECR
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_BASE"

# Build and push bot
echo ""
echo "--- Building stock-intel-bot ---"
docker build -t stock-intel-bot -f "$SRC_DIR/Dockerfile.bot" "$SRC_DIR" --platform linux/arm64 --provenance=false
docker tag stock-intel-bot:latest "$ECR_BASE/stock-intel-bot:latest"
docker push "$ECR_BASE/stock-intel-bot:latest"

# Build and push scanner
echo ""
echo "--- Building stock-intel-scanner ---"
docker build -t stock-intel-scanner -f "$SRC_DIR/Dockerfile.scanner" "$SRC_DIR" --platform linux/arm64 --provenance=false
docker tag stock-intel-scanner:latest "$ECR_BASE/stock-intel-scanner:latest"
docker push "$ECR_BASE/stock-intel-scanner:latest"

# Build and push alert sender
echo ""
echo "--- Building stock-intel-alert-sender ---"
docker build -t stock-intel-alert-sender -f "$SRC_DIR/Dockerfile.alert_sender" "$SRC_DIR" --platform linux/arm64 --provenance=false
docker tag stock-intel-alert-sender:latest "$ECR_BASE/stock-intel-alert-sender:latest"
docker push "$ECR_BASE/stock-intel-alert-sender:latest"

echo ""
echo "=== All images built and pushed ==="
