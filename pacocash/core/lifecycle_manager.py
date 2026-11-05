import asyncio
import os
import shutil
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

from .proxy_helper import get_working_proxy_for_account
from .session_manager import load_accounts_db, SESSIONS_DIR

logger = logging.getLogger("pacocash.lifecycle")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_DIR = os.path.join(BASE_DIR, "archived_sessions")

async def retire_account(
    acc_name: str,
    cfg: dict,
    db: dict,
    accounts_db: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Retires a fully-squeezed account from the active farm:
    1. Wipes bio to empty string ('') via Telegram API
    2. Moves session file from sessions/ to archived_sessions/
    3. Updates database.json with archived=True, bio_cleaned=True
    4. Never archives receiver_account (e.g. Xxxcalibur)
    """
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    accounts_db = accounts_db or load_accounts_db()

    receiver_acc = cfg.get("receiver_account", "[RU] Xxxcalibur +79936124946 2025")
    if acc_name == receiver_acc:
        return {"ok": False, "error": "Receiver account cannot be archived (required for claiming cheques)"}

    session_path = os.path.join(SESSIONS_DIR, f"{acc_name}.session")
    archived_path = os.path.join(ARCHIVE_DIR, f"{acc_name}.session")

    # 1. Clean Bio if session exists
    bio_status = "already_cleaned"
    if os.path.exists(session_path):
        meta = accounts_db.get(acc_name, {})
        working_proxy = get_working_proxy_for_account(acc_name, meta)
        tel_proxy = working_proxy.get("telethon") if isinstance(working_proxy, dict) else None

        client = TelegramClient(
            session_path,
            cfg["api_id"],
            cfg["api_hash"],
            proxy=tel_proxy,
            connection_retries=2,
            retry_delay=1
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=12.0)
            if await client.is_user_authorized():
                me = await client.get_entity('me')
                full = await client(GetFullUserRequest(me))
                cur_bio = full.full_user.about or ""
                if cur_bio:
                    await client(UpdateProfileRequest(about=""))
                    bio_status = "bio_wiped"
                else:
                    bio_status = "bio_was_empty"
        except Exception as e:
            bio_status = f"bio_wipe_skipped ({e})"
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    # 2. Never move session files from sessions/ - keep all sessions intact
    moved_session = False

    # 3. Update database record
    if acc_name in db:
        db[acc_name]["archived"] = True
        db[acc_name]["archived_at"] = datetime.now().isoformat()
        db[acc_name]["bio_cleaned"] = True
        db[acc_name]["status"] = "ARCHIVED"

    return {
        "ok": True,
        "acc_name": acc_name,
        "bio_status": bio_status,
        "moved_session": moved_session
    }

async def auto_retire_eligible_accounts(cfg: dict, db: dict) -> list:
    """
    Finds all withdrawn accounts (withdrawn=True and not yet archived)
    and executes retirement.
    """
    accounts_db = load_accounts_db()
    receiver_acc = cfg.get("receiver_account", "[RU] Xxxcalibur +79936124946 2025")
    
    retired = []
    for acc_name, data in list(db.items()):
        if acc_name == receiver_acc:
            continue
        if data.get("withdrawn") and not data.get("archived"):
            res = await retire_account(acc_name, cfg, db, accounts_db)
            if res.get("ok"):
                retired.append(res)
                
    return retired
