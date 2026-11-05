import asyncio
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

# Ensure UTF-8 output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add pacocash folder to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PACO_DIR = os.path.join(BASE_DIR, "pacocash")
if PACO_DIR not in sys.path:
    sys.path.insert(0, PACO_DIR)

from telethon import TelegramClient
from telethon.tl.types import InputUser
from telethon.tl.functions.messages import StartBotRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.account import UpdateProfileRequest

from pacocash.core.proxy_helper import get_working_proxy_for_account
from pacocash.core.session_manager import load_accounts_db, SESSIONS_DIR
from pacocash.core.smart_chatter import (
    run_smart_chat_session,
    ensure_bio_and_verification,
    get_chat_stats,
    analyze_and_generate_reply,
    is_account_spamblocked,
    REQUIRED_BIO,
    REQUIRED_CHANNELS,
    TARGET_CHAT
)
from pacocash.core.paco_withdraw import attempt_account_withdrawal
from pacocash.core.cryptobot_claimer import claim_check_with_account

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pacocash_runner.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("pacocash.runner")

DATABASE_PATH = os.path.join(PACO_DIR, "database.json")
WITHDRAWALS_PATH = os.path.join(PACO_DIR, "withdrawals.json")
CONFIG_PATH = os.path.join(PACO_DIR, "config.json")
SUMMARY_PATH = os.path.join(BASE_DIR, "pacocash_summary.json")
AUDIT_PATH = os.path.join(PACO_DIR, "audit_108_paco_status.json")

RUNNER_STATE = {
    "status": "IDLE",
    "current_task": None,
    "last_run": None,
    "total_withdrawn_count": 0,
    "total_withdrawn_usdt": 0.0,
    "recent_events": []
}

def log_event(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    logger.info(entry)
    RUNNER_STATE["recent_events"].append(entry)
    if len(RUNNER_STATE["recent_events"]) > 50:
        RUNNER_STATE["recent_events"] = RUNNER_STATE["recent_events"][-50:]

def load_cfg() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config.json: {e}")
    return {
        "api_id": 32293468,
        "api_hash": "0897266f179723de0640905e2f7860f3",
        "receiver_account": "[RU] Xxxcalibur +79936124946 2025",
        "bot_username": "PacoCashBot"
    }

def load_paco_db() -> dict:
    if os.path.exists(DATABASE_PATH):
        try:
            with open(DATABASE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_paco_db(data: dict):
    try:
        with open(DATABASE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving database.json: {e}")

def load_withdrawals() -> list:
    if os.path.exists(WITHDRAWALS_PATH):
        try:
            with open(WITHDRAWALS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def record_withdrawal(acc_name: str, amount: float, check_url: str, receiver: str):
    withdrawals = load_withdrawals()
    entry = {
        "account": acc_name,
        "amount": amount,
        "check_url": check_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "claimed_by": receiver,
        "status": "CLAIMED"
    }
    withdrawals.append(entry)
    try:
        with open(WITHDRAWALS_PATH, "w", encoding="utf-8") as f:
            json.dump(withdrawals, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving withdrawals.json: {e}")

    # Also update database.json
    db = load_paco_db()
    if acc_name in db:
        db[acc_name]["withdrawn"] = True
        db[acc_name]["withdrawn_amount"] = amount
        db[acc_name]["check_url"] = check_url
        db[acc_name]["status"] = "ARCHIVED"
        save_paco_db(db)

def load_summary() -> dict:
    withdrawals = load_withdrawals()
    total_usdt = sum(w.get("amount", 0.0) for w in withdrawals if w.get("claimed_by") or w.get("status") == "CLAIMED")
    db = load_paco_db()

    withdrawn_accs = {w.get("account") for w in withdrawals}
    stuck_parents = [
        k for k, v in db.items()
        if k not in withdrawn_accs and v.get("available", 0.0) >= 0.5 and v.get("status") != "ARCHIVED"
    ]

    summary = {
        "status": RUNNER_STATE["status"],
        "current_task": RUNNER_STATE.get("current_task") or "Активация очереди рефералов",
        "current_progress": RUNNER_STATE.get("current_progress") or "0/51 смс (0%)",
        "eta_minutes": RUNNER_STATE.get("eta_minutes", 25),
        "payout_interval": "~25–30 минут на 1 выплату",
        "next_payout_amount": "~$1.00 - $1.50 USDT",
        "last_run": RUNNER_STATE["last_run"],
        "total_withdrawn_count": len(withdrawals),
        "total_withdrawn_usdt": round(total_usdt, 2),
        "stuck_parents_count": len(stuck_parents),
        "receiver_account": load_cfg().get("receiver_account"),
        "recent_events": RUNNER_STATE["recent_events"][-20:]
    }

    try:
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return summary

def build_execution_plan() -> List[dict]:
    """
    Pairs each unpaid parent ($0.50 available) with:
    1. An existing leaf child assigned to them (if any).
    2. OR a clean account that has never touched PacoCash.
    """
    db = load_paco_db()
    withdrawals = load_withdrawals()
    withdrawn_set = {w.get("account") for w in withdrawals}

    # Available session files
    valid_sessions = {
        f[:-8] for f in os.listdir(SESSIONS_DIR)
        if f.endswith(".session") and not f.startswith("temp_")
    }

    # 1. Parents needing activation
    parents = []
    for acc_name, data in db.items():
        if acc_name in withdrawn_set or acc_name not in valid_sessions:
            continue
        avail = data.get("available", 0.0)
        own_ref = data.get("own_ref_code")
        if avail >= 0.5 and own_ref:
            parents.append((acc_name, own_ref, avail, data.get("children", [])))

    # 2. Existing leaf children (balance 0.0, assigned to parents)
    leaf_children = []
    for acc_name, data in db.items():
        if acc_name in withdrawn_set or acc_name not in valid_sessions:
            continue
        if data.get("available", 0.0) == 0.0 and data.get("parent_ref"):
            leaf_children.append((acc_name, data.get("parent_ref")))

    # 3. Clean accounts from audit
    clean_candidates = []
    if os.path.exists(AUDIT_PATH):
        try:
            with open(AUDIT_PATH, "r", encoding="utf-8") as f:
                audit_data = json.load(f)
            for acc in audit_data.get("never_participated", []):
                if acc not in withdrawn_set and acc in valid_sessions and acc not in db:
                    clean_candidates.append(acc)
        except Exception:
            pass

    # Build tasks: Prioritize fresh clean accounts first for maximum reliability and immediate payouts!
    tasks = []
    used_children = set()
    used_parents = set()

    # Step A: Match parents with fresh clean accounts FIRST
    clean_idx = 0
    for p_name, p_ref, p_avail, _ in parents:
        if clean_idx < len(clean_candidates):
            child_name = clean_candidates[clean_idx]
            clean_idx += 1
            tasks.append({
                "parent": p_name,
                "parent_ref_code": p_ref,
                "child": child_name,
                "is_clean": True,
                "target_paid": 51
            })
            used_children.add(child_name)
            used_parents.add(p_name)

    # Step B: Match remaining parents with existing leaf children
    for p_name, p_ref, p_avail, p_children in parents:
        if p_name in used_parents:
            continue
        matched_child = None
        for c in p_children:
            if c in valid_sessions and c not in withdrawn_set and c not in used_children:
                matched_child = c
                break
        if matched_child:
            tasks.append({
                "parent": p_name,
                "parent_ref_code": p_ref,
                "child": matched_child,
                "is_clean": False,
                "target_paid": 51
            })
            used_children.add(matched_child)
            used_parents.add(p_name)

    log_event(f"Built execution plan: {len(tasks)} tasks queued for activation and payout.")
    return tasks

async def withdraw_and_claim_account(
    acc_name: str,
    cfg: dict,
    accounts_db: dict
) -> Dict[str, Any]:
    """
    Attempts withdrawal for an account and automatically claims cheque via Xxxcalibur.
    """
    s_path = os.path.join(SESSIONS_DIR, f"{acc_name}.session")
    if not os.path.exists(s_path):
        return {"ok": False, "error": "Session file not found"}

    meta = accounts_db.get(acc_name, {})
    working_proxy = get_working_proxy_for_account(acc_name, meta)
    is_cloud = bool(os.environ.get("RENDER") or os.environ.get("PORT"))
    tel_proxy = None if is_cloud else (working_proxy.get("telethon") if isinstance(working_proxy, dict) else None)

    client = TelegramClient(
        s_path[:-8],
        cfg["api_id"],
        cfg["api_hash"],
        proxy=tel_proxy,
        connection_retries=2,
        timeout=12.0,
        flood_sleep_threshold=24,
        catch_up=False,
        **meta.get("device", {})
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            return {"ok": False, "error": "Unauthorized session"}

        log_event(f"Attempting withdrawal for '{acc_name}'...")
        w_res = await attempt_account_withdrawal(client, acc_name, meta=meta, amount=1.0)
        await client.disconnect()

        if w_res.get("ok") and w_res.get("check_url"):
            check_url = w_res["check_url"]
            amount = w_res.get("amount", 1.0)
            receiver = cfg.get("receiver_account", "[RU] Xxxcalibur +79936124946 2025")
            log_event(f"Cheque generated for {acc_name}: {check_url}. Claiming to {receiver}...")

            claim_res = await claim_check_with_account(check_url, receiver_account=receiver, cfg=cfg)
            if claim_res.get("ok"):
                record_withdrawal(acc_name, amount, check_url, receiver)
                log_event(f"SUCCESS: Claimed ${amount:.2f} USDT from {acc_name} to {receiver}!")
                return {"ok": True, "withdrawn": True, "amount": amount, "check_url": check_url}
            else:
                log_event(f"Warning: Cheque claim failed for {acc_name}: {claim_res.get('error')}")
                return {"ok": False, "error": claim_res.get("error"), "check_url": check_url}

        return w_res

    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        log_event(f"Error withdrawing {acc_name}: {e}")
        return {"ok": False, "error": str(e)}

async def execute_task(task: dict, cfg: dict, accounts_db: dict) -> bool:
    """
    Executes a single pairing task:
    1. Sets up child account (referral onboarding, bio, channels)
    2. Runs smart context-aware chatting until 51 messages are paid
    3. Withdraws & claims parent account
    4. Checks & withdraws child account if eligible
    """
    child_name = task["child"]
    parent_name = task["parent"]
    parent_ref = task["parent_ref_code"]
    is_clean = task.get("is_clean", False)
    target_paid = task.get("target_paid", 51)

    RUNNER_STATE["current_task"] = f"{child_name} -> {parent_name}"
    log_event(f"Starting task: Child '{child_name}' activating Parent '{parent_name}' (ref={parent_ref})")

    s_path = os.path.join(SESSIONS_DIR, f"{child_name}.session")
    if not os.path.exists(s_path):
        log_event(f"Error: Child session not found: {s_path}")
        return False

    meta = accounts_db.get(child_name, {})
    working_proxy = get_working_proxy_for_account(child_name, meta)
    is_cloud = bool(os.environ.get("RENDER") or os.environ.get("PORT"))
    tel_proxy = None if is_cloud else (working_proxy.get("telethon") if isinstance(working_proxy, dict) else None)

    client = TelegramClient(
        s_path[:-8],
        cfg["api_id"],
        cfg["api_hash"],
        proxy=tel_proxy,
        connection_retries=2,
        timeout=12.0,
        flood_sleep_threshold=24,
        catch_up=False,
        **meta.get("device", {})
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            log_event(f"Error: Child {child_name} is unauthorized")
            db = load_paco_db()
            db[child_name] = {"status": "UNAUTHORIZED", "error": "Session unauthorized"}
            save_paco_db(db)
            return False

        # Check Telegram SpamBot status before attempting work
        is_spamblocked, spambot_status = await is_account_spamblocked(client)
        if is_spamblocked:
            log_event(f"Child {child_name} is restricted by Telegram SpamBot ({spambot_status}). Skipping child.")
            db = load_paco_db()
            db[child_name] = {"status": "SPAMBLOCK", "error": spambot_status}
            save_paco_db(db)
            await client.disconnect()
            return False

        # 1. Onboard if clean
        if is_clean:
            bot_input = await client.get_input_entity("PacoCashBot")
            log_event(f"Onboarding clean child '{child_name}' with parent ref '{parent_ref}'...")
            await client(StartBotRequest(bot=bot_input, peer=bot_input, start_param=parent_ref))
            await asyncio.sleep(2.5)

            # Record in database.json
            db = load_paco_db()
            db[child_name] = {
                "parent_ref": parent_ref,
                "status": "ACTIVE",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            if parent_name in db:
                ch_list = db[parent_name].setdefault("children", [])
                if child_name not in ch_list:
                    ch_list.append(child_name)
            save_paco_db(db)

        # 2 & 3. Smart Context-Aware Chat Session (automatically handles bio, channels and 51 messages)
        log_event(f"Entering @ChatPaco with '{child_name}' to reach {target_paid} messages (ETA ~25 мин)...")
        def on_chat_progress(acc, cur, tot, desc):
            rem = max(0, tot - cur)
            eta_m = max(1, round(rem * 0.55))
            pct = min(100, round((cur / max(1, tot)) * 100))
            RUNNER_STATE["current_progress"] = f"{cur}/{tot} смс ({pct}%)"
            RUNNER_STATE["eta_minutes"] = eta_m
            log_event(f"[{acc}] {desc} | До выплаты ~$1.00 USDT: ~{eta_m} мин")
            load_summary()

        chat_res = await run_smart_chat_session(
            client=client,
            account_name=child_name,
            target_paid=target_paid,
            progress_callback=on_chat_progress
        )

        await client.disconnect()

        if not chat_res.get("ok"):
            log_event(f"Chat session did not achieve goal for '{child_name}': {chat_res.get('error')}")
            db = load_paco_db()
            db[child_name] = {"status": "RESTRICTED", "error": str(chat_res.get('error'))}
            save_paco_db(db)
            return False

        log_event(f"Child '{child_name}' reached 51 paid messages! Qualifying referral complete.")

        # 4. Trigger Parent Withdrawal
        log_event(f"Parent '{parent_name}' is now unlocked. Triggering withdrawal...")
        await asyncio.sleep(3.0)
        parent_w_res = await withdraw_and_claim_account(parent_name, cfg, accounts_db)
        log_event(f"Parent '{parent_name}' withdrawal result: {parent_w_res}")

        # 5. Check Child Withdrawal
        await asyncio.sleep(2.0)
        child_w_res = await withdraw_and_claim_account(child_name, cfg, accounts_db)
        log_event(f"Child '{child_name}' withdrawal result: {child_w_res}")

        load_summary()
        return True

    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        log_event(f"Error executing task for {child_name}: {e}")
        return False

async def run_pacocash_cycle(max_tasks: Optional[int] = None):
    """
    Main autonomous cycle:
    Loads execution plan and processes tasks sequentially.
    """
    global RUNNER_STATE
    RUNNER_STATE["status"] = "RUNNING"
    RUNNER_STATE["last_run"] = datetime.now(timezone.utc).isoformat()
    load_summary()

    cfg = load_cfg()
    accounts_db = load_accounts_db()
    tasks = build_execution_plan()

    if max_tasks:
        tasks = tasks[:max_tasks]

    log_event(f"=== Starting PacoCash Autonomous Cycle with {len(tasks)} tasks ===")

    success_count = 0
    for idx, task in enumerate(tasks, 1):
        log_event(f"--- Task {idx}/{len(tasks)} ---")
        ok = await execute_task(task, cfg, accounts_db)
        if ok:
            success_count += 1
        # Moderate pause between tasks
        await asyncio.sleep(15.0)

    RUNNER_STATE["status"] = "IDLE"
    RUNNER_STATE["current_task"] = None
    load_summary()
    log_event(f"=== Completed PacoCash Cycle. Successfully completed {success_count}/{len(tasks)} tasks ===")

async def start_pacocash_daemon():
    """
    Background daemon for sniper_server.py on Render:
    Periodically checks status and runs scheduled cycles.
    """
    logger.info("Starting PacoCash daemon for Render...")
    # Wait for server startup
    await asyncio.sleep(30)
    while True:
        try:
            tasks = build_execution_plan()
            if tasks:
                log_event(f"PacoCash daemon found {len(tasks)} queued tasks. Launching batch...")
                # Test single task first as requested
                await run_pacocash_cycle(max_tasks=1)
            else:
                log_event("PacoCash daemon: All accounts processed and withdrawn. Idle.")
        except Exception as e:
            logger.error(f"PacoCash daemon error: {e}")

        # Wait 30 minutes before next check
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(run_pacocash_cycle(max_tasks=1))
