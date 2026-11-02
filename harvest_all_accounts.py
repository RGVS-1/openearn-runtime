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
        logging.FileHandler("harvest.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("harvester")

DATABASE_PATH = "database.json"
CONFIG_PATH = "config.json"
ACCOUNTS_DB_PATH = "accounts_db.json" if os.path.exists("accounts_db.json") else r"C:\Users\hoaki\Desktop\RB_Autimatic\accounts_db.json"
APP_API_BASE = "https://app.theopenearn.info/api"

async def process_single_account(acc_name: str, meta: dict, cfg: dict, db: dict) -> dict:
    sess_path = os.path.join("sessions", f"{acc_name}.session")
    if not os.path.exists(sess_path):
        return {"account": acc_name, "status": "skipped", "reason": "no_session"}

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
        await asyncio.wait_for(client.connect(), timeout=18.0)
        if not await client.is_user_authorized():
            return {"account": acc_name, "status": "error", "reason": "unauthorized"}

        app_bot = await client.get_entity("TheOpenEarnAppBot")
        res = await client(RequestAppWebViewRequest(
            peer=app_bot,
            app=InputBotAppShortName(bot_id=await client.get_input_entity(app_bot), short_name='run'),
            platform='android',
            start_param='ref_we4ses4p'
        ))

        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(res.url).fragment)
        init_data = parsed.get('tgWebAppData', [''])[0]
    except Exception as e:
        return {"account": acc_name, "status": "error", "reason": f"mtproto_err: {e}"}
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    if not init_data:
        return {"account": acc_name, "status": "error", "reason": "no_init_data"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"tma {init_data}",
        "User-Agent": user_agent,
        "Origin": "https://app.theopenearn.info",
        "Referer": "https://app.theopenearn.info/"
    }

    acc_result = {
        "account": acc_name,
        "status": "success",
        "checkin_claimed": False,
        "tapper_claimed": False,
        "case_opened": False,
        "case_prize": None,
        "tot_balance": 0,
        "stars_balance": "0"
    }

    # 1. Claim Checkin (if not already claimed)
    try:
        r_ci = requests.post(f"{APP_API_BASE}/checkin/claim", headers=headers, json={"platform": "android"}, timeout=10)
        if r_ci.status_code == 200:
            acc_result["checkin_claimed"] = True
            logger.info(f"[{acc_name}] Daily checkin claimed: +15 TOT")
    except Exception as e:
        logger.debug(f"[{acc_name}] Checkin error: {e}")

    # 2. Tapper Game (+100 TOT)
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
                    acc_result["tapper_claimed"] = True
                    logger.info(f"[{acc_name}] Tapper complete: +100 TOT!")
            elif t_data.get("cooldown_until"):
                logger.info(f"[{acc_name}] Tapper already on cooldown until {t_data.get('cooldown_until')}")
    except Exception as e:
        logger.debug(f"[{acc_name}] Tapper error: {e}")

    # 3. Daily Free Case (Win Stars & Gifts)
    try:
        r_case = requests.post(f"{APP_API_BASE}/case/open", headers=headers, timeout=10)
        if r_case.status_code == 200:
            c_data = r_case.json()
            acc_result["case_opened"] = True
            acc_result["case_prize"] = f"{c_data.get('label')} {c_data.get('prize_type')}"
            logger.info(f"[{acc_name}] Won Daily Case: {acc_result['case_prize']}!")
    except Exception as e:
        logger.debug(f"[{acc_name}] Case open error: {e}")

    # 4. Social share pings
    try:
        requests.post(f"{APP_API_BASE}/case/friends/shared", headers=headers, timeout=6)
        requests.post(f"{APP_API_BASE}/case/story/shared", headers=headers, timeout=6)
    except Exception:
        pass

    # 5. Fetch updated User Profile
    try:
        r_user = requests.get(f"{APP_API_BASE}/user", headers=headers, timeout=10)
        if r_user.status_code == 200:
            u_data = r_user.json()
            acc_result["tot_balance"] = u_data.get("tot_balance", 0)
            acc_result["stars_balance"] = str(u_data.get("balance", "0"))
            if not db.get(acc_name):
                db[acc_name] = {}
            db[acc_name]["tot_balance"] = acc_result["tot_balance"]
            db[acc_name]["balance_stars"] = acc_result["stars_balance"]
            db[acc_name]["user_id"] = u_data.get("id")
            db[acc_name]["username"] = u_data.get("username")
            db[acc_name]["referral_code"] = u_data.get("referral_code")
            db[acc_name]["status"] = "COMPLETED"
            db[acc_name]["last_harvest_at"] = datetime.utcnow().isoformat()
    except Exception as e:
        logger.debug(f"[{acc_name}] User profile fetch error: {e}")

    return acc_result

async def main():
    logger.info("=========================================================")
    logger.info("Starting MAX TOT & REWARDS Harvest across ALL accounts...")
    logger.info("=========================================================")

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

    # Target: All accounts from RB_Autimatic (excluding frozen Tamosya)
    target_accounts = []
    # 1. Root account first
    root_acc = "[RU] Xxxcalibur +79936124946 2025"
    if root_acc in rb_accs:
        target_accounts.append(root_acc)

    # 2. All other accounts
    for acc in rb_accs:
        if acc != root_acc and acc != "[KZ] Tamosyaaaaaa +77052241850 2026":
            target_accounts.append(acc)

    total = len(target_accounts)
    logger.info(f"Total valid working accounts to harvest: {total}")

    success_count = 0
    tapper_count = 0
    cases_won = []
    total_tot = 0

    start_time = time.time()

    for idx, acc_name in enumerate(target_accounts, 1):
        meta = rb_accs.get(acc_name, {})
        logger.info(f"[{idx}/{total}] Processing: {acc_name}...")
        
        res = await process_single_account(acc_name, meta, cfg, db)
        
        if res.get("status") == "success":
            success_count += 1
            if res.get("tapper_claimed"):
                tapper_count += 1
            if res.get("case_opened"):
                cases_won.append(f"{acc_name}: {res.get('case_prize')}")
            total_tot += res.get("tot_balance", 0)
            logger.info(f"[{idx}/{total}] OK: Balance = {res.get('tot_balance')} TOT | Stars = {res.get('stars_balance')}")
        else:
            logger.warning(f"[{idx}/{total}] SKIPPED/ERR: {res.get('reason')}")

        # Save database periodically
        if idx % 5 == 0 or idx == total:
            with open(DATABASE_PATH, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)

        # Brief delay to respect rate limits
        await asyncio.sleep(1.0)

    elapsed = round(time.time() - start_time, 1)

    logger.info("=========================================================")
    logger.info("HARVEST COMPLETE!")
    logger.info(f"Time elapsed: {elapsed} seconds")
    logger.info(f"Accounts processed successfully: {success_count}/{total}")
    logger.info(f"Tappers completed (+100 TOT each): {tapper_count}")
    logger.info(f"Free Cases opened: {len(cases_won)}")
    logger.info(f"Total Farm TOT Balance: {total_tot:,} TOT")
    logger.info("=========================================================")

if __name__ == "__main__":
    asyncio.run(main())
