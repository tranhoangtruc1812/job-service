import logging
import os
from typing import Any, Dict, Optional

import requests


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("job-worker")

SOURCE_API_URL = os.getenv("SOURCE_API_URL", "https://api.github.com/zen")
SOURCE_API_METHOD = os.getenv("SOURCE_API_METHOD", "GET").upper()
SOURCE_API_TIMEOUT = int(os.getenv("SOURCE_API_TIMEOUT", "15"))

SOURCE_API_ACCESS_TOKEN = os.getenv("SOURCE_API_ACCESS_TOKEN", "")
SOURCE_API_AUTH_HEADER = os.getenv("SOURCE_API_AUTH_HEADER", "Authorization")
SOURCE_API_TOKEN_PREFIX = os.getenv("SOURCE_API_TOKEN_PREFIX", "Bearer")

TOKEN_URL = os.getenv("TOKEN_URL", "")
TOKEN_GRANT_TYPE = os.getenv("TOKEN_GRANT_TYPE", "client_credentials")
TOKEN_CLIENT_ID = os.getenv("TOKEN_CLIENT_ID", "")
TOKEN_CLIENT_SECRET = os.getenv("TOKEN_CLIENT_SECRET", "")
TOKEN_SCOPE = os.getenv("TOKEN_SCOPE", "")
TOKEN_FIELD_NAME = os.getenv("TOKEN_FIELD_NAME", "access_token")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_PARSE_MODE = os.getenv("TELEGRAM_PARSE_MODE", "HTML")


def _build_source_headers(access_token: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if access_token:
        headers[SOURCE_API_AUTH_HEADER] = f"{SOURCE_API_TOKEN_PREFIX} {access_token}".strip()
    return headers


def refresh_access_token() -> str:
    """Fetch a new access token from token endpoint."""
    if not TOKEN_URL:
        raise RuntimeError("TOKEN_URL is required when refreshing token")
    if not TOKEN_CLIENT_ID or not TOKEN_CLIENT_SECRET:
        raise RuntimeError("TOKEN_CLIENT_ID and TOKEN_CLIENT_SECRET are required")

    payload: Dict[str, str] = {
        "grant_type": TOKEN_GRANT_TYPE,
        "client_id": TOKEN_CLIENT_ID,
        "client_secret": TOKEN_CLIENT_SECRET,
    }
    if TOKEN_SCOPE:
        payload["scope"] = TOKEN_SCOPE

    logger.info("Refreshing access token via %s", TOKEN_URL)
    response = requests.post(TOKEN_URL, data=payload, timeout=SOURCE_API_TIMEOUT)
    response.raise_for_status()
    token_data = response.json()

    new_token = token_data.get(TOKEN_FIELD_NAME)
    if not new_token:
        raise RuntimeError(f"Token field '{TOKEN_FIELD_NAME}' not found in response")

    return str(new_token)


def call_source_api(access_token: Optional[str]) -> requests.Response:
    headers = _build_source_headers(access_token or "")
    logger.info("Calling source API: %s", SOURCE_API_URL)
    if SOURCE_API_METHOD == "POST":
        return requests.post(SOURCE_API_URL, headers=headers, timeout=SOURCE_API_TIMEOUT)
    return requests.get(SOURCE_API_URL, headers=headers, timeout=SOURCE_API_TIMEOUT)


def fetch_data() -> Dict[str, Any]:
    global SOURCE_API_ACCESS_TOKEN

    response = call_source_api(SOURCE_API_ACCESS_TOKEN)

    if response.status_code == 401 and TOKEN_URL:
        logger.warning("Source API token expired (401). Refreshing token and retrying...")
        SOURCE_API_ACCESS_TOKEN = refresh_access_token()
        response = call_source_api(SOURCE_API_ACCESS_TOKEN)

    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def build_message(data: Dict[str, Any]) -> str:
    return (
        "<b>Job Service Update</b>\n"
        f"Source: <code>{SOURCE_API_URL}</code>\n"
        f"Data: <code>{str(data)[:3000]}</code>"
    )


def send_to_telegram(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": TELEGRAM_PARSE_MODE,
    }
    response = requests.post(telegram_url, json=payload, timeout=SOURCE_API_TIMEOUT)
    response.raise_for_status()


def run_job() -> None:
    logger.info("Worker job started")
    data = fetch_data()
    message = build_message(data)
    send_to_telegram(message)
    logger.info("Worker job done")


if __name__ == "__main__":
    run_job()
