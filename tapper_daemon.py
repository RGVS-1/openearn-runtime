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
DATABASE_PATH = "database.json"
ACCOUNTS_DB_PATH = "accounts_db.json" if os.path.exists("accounts_db.json") else r"C:\Users\hoaki\Desktop\RB_Autimatic\accounts_db.json"
APP_API_BASE = "https://app.theopenearn.info/api"

# Cache for init_data: {acc_name: (init_data, timestamp)}
INITDATA_CACHE = {}

async def get_init_data_with_fallback(acc_name: str, meta: dict, cfg: dict) -> str:
    # Check cache first (valid for 2 hours)
    now = time.time()
    if acc_name in INITDATA_CACHE:
        cached_data, cached_at = INITDATA_CACHE[acc_name]
        if now - cached_at < 7200:
            return cached_data

    sess_path = os.path.join("sessions", f"{acc_name}.session")
    if not os.path.exists(sess_path):
        return None

    dev = meta.get("device", {})
    proxy = meta.get("proxy", {}).get("telethon")
    proxies_to_try = [None, proxy] if (os.environ.get("RENDER") or not proxy) else [proxy, None]

    init_data = None
    for cur_proxy in proxies_to_try:
        client = TelegramClient(
            sess_path,
            cfg["api_id"],
            cfg["api_hash"],
            proxy=cur_proxy,
            device_model=dev.get("device_model", "Desktop"),
            system_version=dev.get("system_version", "Windows 11 x64"),
            app_version=dev.get("app_version", "4.16.8 x64"),
            system_lang_code=dev.get("system_lang_code", "ru-RU"),
            lang_code=dev.get("lang_code", "ru"),
            connection_retries=1
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=12.0)
            if not await client.is_user_authorized():
                return None
            app_bot = await client.get_entity("TheOpenEarnAppBot")
            res = await client(RequestAppWebViewRequest(
                peer=app_bot,
                app=InputBotAppShortName(bot_id=await client.get_input_entity(app_bot), short_name='run'),
                platform='android',
                start_param='ref_we4ses4p'
            ))
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(res.url).fragment)
            init_data = parsed.get('tgWebAppData', [''])[0]
            if init_data:
                INITDATA_CACHE[acc_name] = (init_data, now)
                break
        except Exception:
            continue
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    return init_data

async def tap_account(acc_name: str, meta: dict, cfg: dict, db: dict = None) -> int:
    init_data = await get_init_data_with_fallback(acc_name, meta, cfg)
    if not init_data:
        return 0

    user_agent = meta.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"tma {init_data}",
        "User-Agent": user_agent,
        "Origin": "https://app.theopenearn.info",
        "Referer": "https://app.theopenearn.info/"
    }

    tapped_earned = 0
    try:
        # 1. Daily Check-in (+15..30 TOT)
        try:
            r_ci = requests.post(f"{APP_API_BASE}/checkin/claim", headers=headers, json={"platform": "android"}, timeout=5)
            if r_ci.status_code == 200:
                logger.info(f"[{acc_name}] Daily check-in claimed!")
        except Exception:
            pass

        # 2. Daily Free Case (Win Stars & Gifts)
        try:
            r_case = requests.post(f"{APP_API_BASE}/case/open", headers=headers, timeout=5)
            if r_case.status_code == 200:
                c_data = r_case.json()
                logger.info(f"[{acc_name}] 🎁 Won Daily Free Case: {c_data.get('prize_amount')} Stars / {c_data.get('label')}!")
                try:
                    requests.post(f"{APP_API_BASE}/case/friends/shared", headers=headers, timeout=3)
                    requests.post(f"{APP_API_BASE}/case/story/shared", headers=headers, timeout=3)
                except Exception:
                    pass
        except Exception:
            pass

        # 3. Tapper Game (+100 TOT)
        r_tap_st = requests.get(f"{APP_API_BASE}/earn", headers=headers, timeout=10)
        if r_tap_st.status_code == 401:
            # Token expired, clear cache
            INITDATA_CACHE.pop(acc_name, None)
            return 0

        if r_tap_st.status_code == 200:
            t_data = r_tap_st.json()
            req_taps = t_data.get("taps_required", 100)
            cur_prog = t_data.get("cycle_progress", 0)
            needed = max(0, req_taps - cur_prog)
            if needed > 0 and not t_data.get("cooldown_until"):
                r_tap = requests.post(f"{APP_API_BASE}/earn", headers=headers, json={"taps": needed}, timeout=10)
                if r_tap.status_code == 200:
                    tapped_earned = 100
                    logger.info(f"[{acc_name}] +100 TOT tapped!")

        # 4. Always fetch latest user profile to keep database.json synced with real-time balances
        r_user = requests.get(f"{APP_API_BASE}/user", headers=headers, timeout=10)
        if r_user.status_code == 200:
            u_data = r_user.json()
            real_tot = u_data.get("tot_balance", 0)
            real_stars = str(u_data.get("balance", "0"))

            # 5. Lucky Wheel Auto-spin (if accumulated >= 0.25 Stars)
            try:
                if float(real_stars) >= 0.25:
                    r_spin = requests.post(f"{APP_API_BASE}/wheel/spin", headers=headers, json={"is_paid": True}, timeout=6)
                    if r_spin.status_code == 200:
                        s_data = r_spin.json()
                        logger.info(f"[{acc_name}] 🎰 Lucky Wheel won: {s_data.get('prize_amount')} Stars / {s_data.get('prize_type')}!")
                        real_stars = str(s_data.get("new_balance", real_stars))
            except Exception:
                pass

            if db is not None:
                if acc_name not in db:
                    db[acc_name] = {}
                db[acc_name]["tot_balance"] = real_tot
                db[acc_name]["balance_stars"] = real_stars
                db[acc_name]["last_tap_at"] = datetime.utcnow().isoformat()
    except Exception as e:
        logger.debug(f"[{acc_name}] Tap error: {e}")

    return tapped_earned

async def run_loop(max_rounds: int = 1):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    with open(ACCOUNTS_DB_PATH, "r", encoding="utf-8") as f:
        rb_accs = json.load(f)

    db = {}
    if os.path.exists(DATABASE_PATH):
        try:
            with open(DATABASE_PATH, "r", encoding="utf-8") as f:
                db = json.load(f)
        except Exception:
            db = {}

    target_accounts = [
        acc for acc in rb_accs 
        if acc != "[KZ] Tamosyaaaaaa +77052241850 2026"
    ]

    logger.info(f"⚡ Tapper Loop: Starting cycle for {len(target_accounts)} accounts...")

    for round_num in range(1, max_rounds + 1):
        round_start = time.time()
        round_earned = 0

        for idx, acc in enumerate(target_accounts, 1):
            earned = await tap_account(acc, rb_accs[acc], cfg, db)
            round_earned += earned
            if idx % 5 == 0 or idx == len(target_accounts):
                # Save database periodically so dashboard updates live
                try:
                    with open(DATABASE_PATH, "w", encoding="utf-8") as f:
                        json.dump(db, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
            await asyncio.sleep(0.3)

        elapsed = round(time.time() - round_start, 1)
        tot_sum = sum(int(v.get("tot_balance", 0) or 0) for v in db.values())
        logger.info(f"✅ Tapper Cycle Complete in {elapsed}s! Total Farm Balance: {tot_sum:,} TOT (+{round_earned} this cycle).")

if __name__ == "__main__":
    asyncio.run(run_loop())
