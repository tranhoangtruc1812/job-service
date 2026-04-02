import logging
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
load_dotenv()

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

    params: Dict[str, str] = {
        "grantType": TOKEN_GRANT_TYPE,
        "appId": TOKEN_CLIENT_ID,
        "secret": TOKEN_CLIENT_SECRET,
    }
    if TOKEN_SCOPE:
        params["scope"] = TOKEN_SCOPE

    logger.info("Refreshing access token via %s", TOKEN_URL)
    
    token_auth_header = os.getenv("TOKEN_BASIC_AUTH", "Basic cGVkYWNvOlBFREFDTzAx")
    headers = {
        "Authorization": token_auth_header
    }
    
    # Using params=params to attach them as query parameters like the URL example you provided
    response = requests.post(TOKEN_URL, headers=headers, params=params, timeout=SOURCE_API_TIMEOUT, verify=False)
    
    # fallback to GET if POST is not allowed
    if response.status_code == 405:
        response = requests.get(TOKEN_URL, headers=headers, params=params, timeout=SOURCE_API_TIMEOUT, verify=False)
        
    response.raise_for_status()
    token_data = response.json()

    # Handling nested data responses in case the token is inside a data object
    new_token = None
    if TOKEN_FIELD_NAME in token_data:
        new_token = token_data[TOKEN_FIELD_NAME]
    elif "data" in token_data and isinstance(token_data["data"], dict):
        new_token = token_data["data"].get(TOKEN_FIELD_NAME)

    if not new_token:
        raise RuntimeError(f"Token field '{TOKEN_FIELD_NAME}' not found in response")

    return str(new_token)


def call_source_api(access_token: Optional[str]) -> requests.Response:
    headers = _build_source_headers(access_token or "")
    
    station_id = os.getenv("SOURCE_API_STATION_ID", "1609d29e-93f9-4d0e-8b56-eb03bb39491b")
    
    # Calculate dates dynamically
    now = datetime.now()
    start_date = now.replace(day=1).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")
    
    params = {
        "dataType": "kdtd",
        "endDate": end_date,
        "page": 0,
        "pageSize": 10,
        "startDate": start_date,
        "stationId": station_id
    }
    logger.info("Calling source API %s with params %s", SOURCE_API_URL, params)
    if SOURCE_API_METHOD == "POST":
        return requests.post(SOURCE_API_URL + "/minute", headers=headers, params=params, timeout=SOURCE_API_TIMEOUT)
    return requests.get(SOURCE_API_URL + "/minute", headers=headers, params=params, timeout=SOURCE_API_TIMEOUT)


def fetch_data() -> Dict[str, Any]:
    global SOURCE_API_ACCESS_TOKEN

    SOURCE_API_ACCESS_TOKEN = refresh_access_token()
    response = call_source_api(SOURCE_API_ACCESS_TOKEN)

    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}



def build_message(data: Dict[str, Any]) -> str:
    try:
        run_time_minutes = int(os.getenv("RUN_TIME", "20"))
    except ValueError:
        run_time_minutes = 20

    cutoff_time = datetime.now() - timedelta(minutes=run_time_minutes + 20)

    items = []
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        items = data["data"].get("items", [])

    filtered_items = []
    for item in items:
        time_str = item.get("time")
        if time_str:
            try:
                item_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                if item_time >= cutoff_time:
                    filtered_items.append(item)
            except ValueError:
                pass

    if not items:
        # Fallback nếu API trả về cấu trúc khác
        return (
            "<b>Job Service Update</b>\n"
            f"Source: <code>{SOURCE_API_URL}</code>\n"
            f"Data: <code>{str(data)[:3000]}</code>"
        )
        
    if not filtered_items:
        return "<b>📊 Báo cáo Quan trắc</b>\nKhông có dữ liệu mới trong khoảng thời gian vừa qua."

    # Sắp xếp các record theo thời gian giảm dần (mới nhất lên trước)
    filtered_items.sort(key=lambda x: x.get("time", ""), reverse=True)
    
    # Lấy tối đa 4 record để bảng không bị vượt quá màn hình điện thoại
    display_items = filtered_items[:4]
    
    times = []
    for item in display_items:
        time_str = item.get("time", "")
        # Lấy lấy đoạn giờ:phút, ví dụ "11:15"
        t = time_str[11:16] if len(time_str) >= 16 else "--:--"
        times.append(t)
        
    metrics = {
        "SO2": "so2_v",
        "CO": "co_v",
        "NOx": "nox_v",
        "O2": "o2_v",
        "PM": "pm_v",
        "Flow": "flow_v",
        "Temp": "temp_v",
        "P": "pressure_v",
        "HCl": "hcl_v",
        "T1": "indicator1_v",
        "T2": "indicator2_v"
    }

    def format_val(val):
        if val is None:
            return "-"
        try:
            v = float(val)
            if v >= 1000:
                return f"{v:.0f}"
            if v >= 10:
                return f"{v:.1f}"
            return f"{v:.2f}"
        except (ValueError, TypeError):
            return "-"

    # Tiêu đề cột: Para và các mốc thời gian
    headers_list = ["Para"] + [f"{t:>5}" for t in times]
    header_str = " | ".join(headers_list)
    separator = "-" * len(header_str)
    
    rows = []
    warnings_list = []
    for m_label, m_key in metrics.items():
        row_vals = [f"{m_label[:4]:<4}"]
        for i, item in enumerate(display_items):
            val = item.get(m_key)
            v_str = format_val(val)
            t = times[i]

            if m_label in ["SO2", "CO", "NOx"] and val is not None:
                try:
                    num_val = float(val)
                    if num_val > 250:
                        warnings_list.append(f"🔴 {t} - {m_label}: {num_val} (>250)")
                except (ValueError, TypeError):
                    pass

            if len(v_str) > 5:
                v_str = v_str[:5]
            row_vals.append(f"{v_str:>5}")
            
        rows.append(" | ".join(row_vals))
        
    table_str = "\n".join([header_str, separator] + rows)
    
    warning_str = ""
    if warnings_list:
        warning_str = "\n\n<b>🚨 CẢNH BÁO VƯỢT NGƯỠNG:</b>\n" + "\n".join(warnings_list)
    
    return (
        "<b>📊 KẾT QUẢ QUAN TRẮC GẦN ĐÂY</b>\n"
        f"<i>(Lọc trong {run_time_minutes} phút, {len(filtered_items)} records)</i>\n"
        f"<pre>{table_str}</pre>"
        f"{warning_str}"
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
