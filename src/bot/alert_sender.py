"""Lambda handler for SQS alert delivery — sends alerts to Telegram."""

import json
from datetime import datetime, timezone

from bot import telegram_client
from shared.db import get_alert_config
from shared.config import TELEGRAM_CHAT_ID


def lambda_handler(event, context):
    """SQS → this handler → Telegram message with inline buttons."""
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            chat_id = body.get("chat_id", TELEGRAM_CHAT_ID)
            alert_type = body.get("alert_type", "")
            message = body.get("message", "")
            buttons = body.get("buttons", [])

            config = get_alert_config(chat_id)
            if not config.get("enabled", True):
                continue

            muted_until = config.get("muted_until")
            if muted_until:
                if datetime.now(timezone.utc).isoformat() < muted_until:
                    continue

            if not config.get(alert_type, True):
                continue

            if buttons:
                telegram_client.send_message_with_buttons(chat_id, message, buttons)
            else:
                telegram_client.send_message(chat_id, message)

        except Exception as e:
            print(f"Alert send error: {e}")

    return {"statusCode": 200}
