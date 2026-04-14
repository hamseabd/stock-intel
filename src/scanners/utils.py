"""Scanner utilities — shared helpers for all scanners."""

import json

import boto3

from shared.config import SQS_ALERT_QUEUE_URL, TELEGRAM_CHAT_ID, AWS_REGION
from shared.db import get_positions, get_watchlist
from shared.s3 import write_dashboard_data

_sqs = boto3.client("sqs", region_name=AWS_REGION)


def get_all_scan_tickers() -> list[str]:
    """Get all tickers to scan: portfolio + watchlist."""
    chat_id = TELEGRAM_CHAT_ID
    positions = get_positions(chat_id)
    tickers = list({p["ticker"] for p in positions})
    watchlist = get_watchlist(chat_id)
    return list(set(tickers + watchlist))


def queue_alert(alert_type: str, message: str, buttons: list = None) -> None:
    """Send an alert to the SQS queue for delivery."""
    if not SQS_ALERT_QUEUE_URL:
        print(f"No SQS URL configured. Alert: {message[:100]}")
        return

    body = {
        "chat_id": TELEGRAM_CHAT_ID,
        "alert_type": alert_type,
        "message": message,
        "buttons": buttons or [],
    }
    _sqs.send_message(
        QueueUrl=SQS_ALERT_QUEUE_URL,
        MessageBody=json.dumps(body),
    )


def update_dashboard(filename: str, data: dict) -> None:
    """Write data to S3 for the static dashboard."""
    write_dashboard_data(filename, data)
