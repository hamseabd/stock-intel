"""Telegram Bot API client.

Handles all outgoing communication with the Telegram API: sending messages,
inline keyboard buttons, and webhook management. All calls go through _post()
for consistent error handling and testability.
"""

import json
from typing import Optional

import requests

from shared.config import TELEGRAM_BOT_TOKEN
from shared.log import get_logger

logger = get_logger(__name__)

_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
_session = requests.Session()


def _post(endpoint: str, payload: dict, timeout: int = 10) -> dict:
    """Send a request to the Telegram Bot API.

    All public functions in this module call this method, making it the single
    point to mock in tests.

    Args:
        endpoint: Telegram API method (e.g. "sendMessage")
        payload: Request body as dict
        timeout: HTTP timeout in seconds

    Returns:
        Telegram API response as dict
    """
    resp = _session.post(f"{_BASE_URL}/{endpoint}", json=payload, timeout=timeout)
    result = resp.json()
    if not result.get("ok"):
        logger.error("Telegram API error", endpoint=endpoint, error=result.get("description", "unknown"))
    return result


def send_message(chat_id: str, text: str, parse_mode: str = "HTML",
                 reply_markup: Optional[dict] = None) -> dict:
    """Send a text message to a Telegram chat.

    Automatically splits messages longer than 4000 chars at line boundaries
    to stay under Telegram's 4096 char limit.

    Args:
        chat_id: Telegram chat ID
        text: Message text (HTML formatted)
        parse_mode: "HTML" or "MarkdownV2"
        reply_markup: Optional inline keyboard markup

    Returns:
        Telegram API response
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    if len(text) > 4000:
        logger.info("Splitting long message", chat_id=chat_id, length=len(text))
        chunks = _split_message(text, 4000)
        saved_markup = payload.pop("reply_markup", None)
        result = {}
        for i, chunk in enumerate(chunks):
            payload["text"] = chunk
            # Only attach reply_markup to the last chunk
            if saved_markup and i == len(chunks) - 1:
                payload["reply_markup"] = saved_markup
            result = _post("sendMessage", payload)
        return result

    return _post("sendMessage", payload)


def send_message_with_buttons(chat_id: str, text: str, buttons: list[list[dict]],
                              parse_mode: str = "HTML") -> dict:
    """Send a message with inline keyboard buttons.

    Args:
        chat_id: Telegram chat ID
        text: Message text
        buttons: Nested list of button dicts, e.g.
                 [[{"text": "Label", "callback_data": "/command"}]]

    Returns:
        Telegram API response
    """
    reply_markup = {"inline_keyboard": buttons}
    return send_message(chat_id, text, parse_mode, reply_markup)


def answer_callback(callback_query_id: str, text: str = "") -> dict:
    """Acknowledge an inline keyboard button press.

    Args:
        callback_query_id: ID from the callback_query event
        text: Optional toast notification text

    Returns:
        Telegram API response
    """
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return _post("answerCallbackQuery", payload)


def set_webhook(url: str) -> dict:
    """Register a webhook URL with Telegram.

    Args:
        url: HTTPS URL that Telegram will POST updates to

    Returns:
        Telegram API response
    """
    logger.info("Setting webhook", url=url)
    return _post("setWebhook", {"url": url})


def _split_message(text: str, max_len: int) -> list[str]:
    """Split long messages at line boundaries to stay under Telegram's limit."""
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            if current:
                chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        chunks.append(current)
    return chunks
