import asyncio
import json
import logging
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("farm_executor.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("executor")

from core.chat_activator import activate_child_account
from core.balance_syncer import fetch_live_bot_balance
from core.paco_withdraw import attempt_account_withdrawal
from core.cryptobot_claimer import claim_check_with_account
from core.proxy_helper import get_working_proxy_for_account
from core.session_manager import load_accounts_db, load_database, save_database, SESSIONS_DIR

CONFIG_FILE = "config.json"
WITHDRAWALS_FILE = "withdrawals.json"

def load_cfg():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_withdrawals():
    if os.path.exists(WITHDRAWALS_FILE):
        try:
            with open(WITHDRAWALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_withdrawals(w_list):
    with open(WITHDRAWALS_FILE, "w", encoding="utf-8") as f:
        json.dump(w_list, f, indent=2, ensure_ascii=False)

async def withdraw_parent(parent_name: str, cfg: dict, db: dict, accounts_db: dict, available_amt: float) -> dict:
    """
    Connects to parent account, triggers withdrawal in PacoCashBot,
    and claims the CryptoBot cheque to receiver account.
    """
    s_path = os.path.join(SESSIONS_DIR, f"{parent_name}.session")
    if not os.path.exists(s_path):
        return {"ok": False, "error": f"Session file not found: {s_path}"}

    receiver_name = cfg.get("receiver_account", "[RU] Xxxcalibur +79936124946 2025")
    meta = accounts_db.get(parent_name, {})
    working_proxy = get_working_proxy_for_account(parent_name, meta)
    tel_proxy = working_proxy.get("telethon") if isinstance(working_proxy, dict) else None

    from telethon import TelegramClient
    client = TelegramClient(
        s_path,
        cfg["api_id"],
        cfg["api_hash"],
        proxy=tel_proxy,
        connection_retries=1,
        timeout=10.0
    )

    try:
        await asyncio.wait_for(client.connect(), timeout=10.0)
        if not await client.is_user_authorized():
            return {"ok": False, "error": "Parent account unauthorized"}

        res = await attempt_account_withdrawal(client, parent_name, meta=meta, amount=available_amt)
        try:
            await client.disconnect()
        except Exception:
            pass

        if not res.get("ok"):
            return res

        check_url = res.get("check_url")
        if check_url:
            logger.info(f"[WITHDRAW] Cheque issued: {check_url} for ${available_amt:.2f}")
            claim_res = await claim_check_with_account(check_url, receiver_account=receiver_name, cfg=cfg)
            res["claim"] = claim_res
            if claim_res.get("ok"):
                logger.info(f"[CLAIM] Cheque claimed successfully to {receiver_name}!")
            else:
                logger.warning(f"[CLAIM] Failed to claim cheque: {claim_res.get('error')}")

        return res

    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}

async def process_single_parent(parent_info: dict, cfg: dict, db: dict, accounts_db: dict):
    parent_name = parent_info["parent"]
    avail = parent_info["avail"]
    alive_children = parent_info["alive_children"]

    logger.info(f"=== Processing Parent: {parent_name} (Current avail: ${avail:.2f}) ===")
    
    needed_boost = 1.00 - avail
    needed_children_cnt = int((needed_boost + 0.49) // 0.5) if needed_boost > 0 else 0
    children_to_activate = alive_children[:needed_children_cnt] if needed_children_cnt > 0 else []

    logger.info(f"Children needed to reach >= $1.00: {len(children_to_activate)}")

    for idx, child_name in enumerate(children_to_activate, 1):
        logger.info(f"[{idx}/{len(children_to_activate)}] Activating child: {child_name}...")
        
        def progress_cb(name, p, total, msg):
            print(f"  [{name}] {msg} ({p}/{total})", flush=True)

        res = await activate_child_account(child_name, cfg, progress_cb=progress_cb)
        if res.get("ok"):
            logger.info(f"  Child {child_name} successfully reached {res.get('paid', 51)} messages!")
        else:
            logger.warning(f"  Child {child_name} activation issue: {res.get('error')}")

    # Check parent live balance
    s_path = os.path.join(SESSIONS_DIR, f"{parent_name}.session")
    meta = accounts_db.get(parent_name, {})
    bal_res = await fetch_live_bot_balance(parent_name, s_path, cfg["api_id"], cfg["api_hash"], meta)
    
    logger.info(f"Live balance for parent {parent_name}: {bal_res}")
    cur_avail = bal_res.get("available", 0.0) if bal_res.get("ok") else avail

    # Update database
    if parent_name in db:
        db[parent_name]["available"] = cur_avail
        if bal_res.get("ok"):
            db[parent_name]["held"] = bal_res.get("held", 0.0)
        save_database(db)

    if cur_avail >= 1.00:
        logger.info(f"Parent {parent_name} has ${cur_avail:.2f} >= $1.00! Triggering withdrawal...")
        w_res = await withdraw_parent(parent_name, cfg, db, accounts_db, cur_avail)
        if w_res.get("ok"):
            logger.info(f"WITHDRAWAL SUCCESSFUL for {parent_name}: {w_res.get('check_url')}")
            if parent_name in db:
                db[parent_name]["withdrawn"] = True
                db[parent_name]["check_url"] = w_res.get("check_url")
                db[parent_name]["status"] = "ARCHIVED"
                save_database(db)
            
            w_list = load_withdrawals()
            w_list.append({
                "account": parent_name,
                "amount": cur_avail,
                "check_url": w_res.get("check_url"),
                "claimed": w_res.get("claim", {}).get("ok", False),
                "timestamp": datetime.now().isoformat()
            })
            save_withdrawals(w_list)
        else:
            logger.warning(f"Withdrawal failed for {parent_name}: {w_res.get('error')}")
    else:
        logger.info(f"Parent {parent_name} available is ${cur_avail:.2f} (< $1.00).")

if __name__ == '__main__':
    print("Auto farm executor ready.")
