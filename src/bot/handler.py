"""Lambda handler for Telegram webhook.

Entry point for all bot interactions. API Gateway forwards Telegram webhook
events here. Routes messages and callback queries to the command system.
"""

import json

from bot import telegram_client
from bot.commands import route_command
from shared.config import TELEGRAM_CHAT_ID
from shared.log import get_logger, Timer

logger = get_logger(__name__)


def lambda_handler(event, context):
    """Process a Telegram webhook event.

    Handles two event types:
    - Regular messages: parse text, route to command handler, send response
    - Callback queries: inline keyboard button presses

    Always returns 200 — Telegram retries on non-200 which would cause duplicate messages.
    """
    chat_id = ""
    try:
        body = json.loads(event.get("body", "{}"))

        # Handle inline keyboard callback
        if "callback_query" in body:
            callback = body["callback_query"]
            chat_id = str(callback["message"]["chat"]["id"])

            # Restrict to configured chat_id
            if TELEGRAM_CHAT_ID and chat_id != TELEGRAM_CHAT_ID:
                logger.warning("Rejected unauthorized callback", chat_id=chat_id)
                return {"statusCode": 200}

            callback_data = callback.get("data", "")
            logger.info("Callback received", chat_id=chat_id, data=callback_data)
            telegram_client.answer_callback(callback["id"], "Processing...")
            with Timer(logger, "route_command", command=callback_data, chat_id=chat_id):
                response = route_command(chat_id, callback_data)
            telegram_client.send_message(chat_id, response)
            return {"statusCode": 200}

        # Handle regular message
        message = body.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip()

        if not chat_id or not text:
            return {"statusCode": 200}

        # Restrict to configured chat_id
        if TELEGRAM_CHAT_ID and chat_id != TELEGRAM_CHAT_ID:
            logger.warning("Rejected unauthorized chat", chat_id=chat_id)
            return {"statusCode": 200}

        logger.info("Message received", chat_id=chat_id, text=text[:100])
        with Timer(logger, "route_command", command=text.split()[0], chat_id=chat_id):
            response = route_command(chat_id, text)
        telegram_client.send_message(chat_id, response)

    except Exception as e:
        logger.error("Handler error", chat_id=chat_id, exc_info=True)
        try:
            if chat_id:
                telegram_client.send_message(chat_id, "Something went wrong. Please try again.")
        except Exception:
            logger.error("Failed to send error message to user", chat_id=chat_id, exc_info=True)

    return {"statusCode": 200}
