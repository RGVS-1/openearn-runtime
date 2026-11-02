import asyncio
import json
import logging
import os
import sys
import time
import urllib.parse
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')

import requests
from telethon import TelegramClient
from telethon.tl.functions.messages import RequestAppWebViewRequest
from telethon.tl.types import InputBotAppShortName

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("tapper_loop.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("tapper_daemon")

CONFIG_PATH = "config.json"
ACCOUNTS_DB_PATH = "accounts_db.json" if os.path.exists("accounts_db.json") else r"C:\Users\hoaki\Desktop\RB_Autimatic\accounts_db.json"
APP_API_BASE = "https://app.theopenearn.info/api"

async def get_init_data(client, account_name: str) -> str:
    app_bot = await client.get_entity("TheOpenEarnAppBot")
    res = await client(RequestAppWebViewRequest(
        peer=app_bot,
        app=InputBotAppShortName(bot_id=await client.get_input_entity(app_bot), short_name='run'),
        platform='android',
        start_param='ref_we4ses4p'
    ))
    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(res.url).fragment)
    return parsed.get('tgWebAppData', [''])[0]

async def tap_account(acc_name: str, meta: dict, cfg: dict) -> int:
    sess_path = os.path.join("sessions", f"{acc_name}.session")
    if not os.path.exists(sess_path):
        return 0

    dev = meta.get("device", {})
    proxy = meta.get("proxy", {}).get("telethon")
    user_agent = meta.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    client = TelegramClient(
        sess_path,
        cfg["api_id"],
        cfg["api_hash"],
        proxy=proxy,
        device_model=dev.get("device_model", "Desktop"),
        system_version=dev.get("system_version", "Windows 11 x64"),
        app_version=dev.get("app_version", "4.16.8 x64"),
        system_lang_code=dev.get("system_lang_code", "ru-RU"),
        lang_code=dev.get("lang_code", "ru"),
        connection_retries=2,
        retry_delay=1
    )

    init_data = None
    try:
        await asyncio.wait_for(client.connect(), timeout=15.0)
        if not await client.is_user_authorized():
            return 0
        init_data = await get_init_data(client, acc_name)
    except Exception as e:
        logger.debug(f"[{acc_name}] MTProto connect error: {e}")
        return 0
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    if not init_data:
        return 0

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"tma {init_data}",
        "User-Agent": user_agent,
        "Origin": "https://app.theopenearn.info",
        "Referer": "https://app.theopenearn.info/"
    }

    try:
        r_tap_st = requests.get(f"{APP_API_BASE}/earn", headers=headers, timeout=10)
        if r_tap_st.status_code == 200:
            t_data = r_tap_st.json()
            req_taps = t_data.get("taps_required", 100)
            cur_prog = t_data.get("cycle_progress", 0)
            needed = max(0, req_taps - cur_prog)
            if needed > 0 and not t_data.get("cooldown_until"):
                r_tap = requests.post(f"{APP_API_BASE}/earn", headers=headers, json={"taps": needed}, timeout=10)
                if r_tap.status_code == 200:
                    logger.info(f"[{acc_name}] +100 TOT tapped!")
                    return 100
    except Exception as e:
        logger.debug(f"[{acc_name}] Tap error: {e}")

    return 0

async def run_loop(max_rounds: int = 100):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    with open(ACCOUNTS_DB_PATH, "r", encoding="utf-8") as f:
        rb_accs = json.load(f)

    target_accounts = [
        acc for acc in rb_accs 
        if acc != "[KZ] Tamosyaaaaaa +77052241850 2026"
    ]

    logger.info(f"Tapper Daemon started with {len(target_accounts)} accounts.")

    for round_num in range(1, max_rounds + 1):
        round_start = time.time()
        round_earned = 0
        logger.info(f"--- STARTING TAP ROUND #{round_num} ---")

        for idx, acc in enumerate(target_accounts, 1):
            earned = await tap_account(acc, rb_accs[acc], cfg)
            round_earned += earned
            await asyncio.sleep(0.5)

        elapsed = time.time() - round_start
        logger.info(f"Round #{round_num} finished! Earned: +{round_earned} TOT in {round(elapsed, 1)}s")

        cooldown_wait = max(10, int(310 - elapsed))
        logger.info(f"Waiting {cooldown_wait} seconds for the next 5-min cooldown window...")
        await asyncio.sleep(cooldown_wait)

if __name__ == "__main__":
    asyncio.run(run_loop())
