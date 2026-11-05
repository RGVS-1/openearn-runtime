import asyncio
import json
import logging
import os
import re
from typing import Dict, Any, Optional

from telethon import TelegramClient
from telethon.tl.types import InputUser
from telethon.tl.functions.messages import StartBotRequest

from .proxy_helper import get_working_proxy_for_account, mark_proxy_dead
from .session_manager import load_accounts_db, SESSIONS_DIR

logger = logging.getLogger("pacocash.claimer")

CONFIG_FILE = "config.json"

def _load_cfg() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

async def claim_check_with_account(
    check_url: str,
    receiver_account: str = "[RU] Xxxcalibur +79936124946 2025",
    cfg: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Connects using receiver account session (e.g. Xxxcalibur),
    activates the CryptoBot cheque, and deposits USDT directly into its wallet.
    Automatically rotates working proxy from RB_Autimatic if 407 or timeout occurs.
    """
    cfg = cfg or _load_cfg()
    s_path = os.path.join(SESSIONS_DIR, f"{receiver_account}.session")
    if not os.path.exists(s_path):
        return {"ok": False, "error": f"Receiver session file not found: {s_path}"}

    # Extract start_param from url (e.g. https://t.me/CryptoBot?start=CQXVmz7PWnd9 -> CQXVmz7PWnd9)
    match_param = re.search(r"start=([a-zA-Z0-9_\-]+)", check_url)
    if not match_param:
        return {"ok": False, "error": f"Invalid check URL: {check_url}"}

    start_param = match_param.group(1)

    accounts_db = load_accounts_db()
    meta = accounts_db.get(receiver_account, {})
    working_proxy = get_working_proxy_for_account(receiver_account, meta)
    prx = working_proxy.get("telethon") if isinstance(working_proxy, dict) else None
    dev = meta.get("device", {
        "device_model": "Desktop", "system_version": "Windows 11 x64",
        "app_version": "4.16.8 x64", "system_lang_code": "ru-RU", "lang_code": "ru"
    })

    client = TelegramClient(
        s_path,
        cfg["api_id"],
        cfg["api_hash"],
        proxy=prx,
        device_model=dev.get("device_model", "Desktop"),
        system_version=dev.get("system_version", "Windows 11 x64"),
        app_version=dev.get("app_version", "4.16.8 x64"),
        connection_retries=2,
        retry_delay=1
    )

    try:
        await asyncio.wait_for(client.connect(), timeout=12.0)
        if not await client.is_user_authorized():
            return {"ok": False, "error": f"Receiver {receiver_account} is UNAUTHORIZED"}

        bot_ent = await client.get_input_entity("CryptoBot")
        bot = InputUser(bot_ent.user_id, bot_ent.access_hash)

        await client(StartBotRequest(
            bot=bot,
            peer=bot,
            start_param=start_param
        ))

        await asyncio.sleep(2.5)

        msgs = await client.get_messages("CryptoBot", limit=2)
        reply_text = msgs[0].text if msgs else ""

        if "Вы получили" in reply_text or "получили" in reply_text.lower():
            return {
                "ok": True,
                "claimed": True,
                "start_param": start_param,
                "message": reply_text
            }
        elif "уже активирован" in reply_text.lower():
            return {
                "ok": True,
                "claimed": False,
                "already_claimed": True,
                "message": reply_text
            }
        else:
            return {
                "ok": True,
                "claimed": True,
                "message": reply_text
            }

    except Exception as e:
        logger.error(f"Error claiming check {check_url} by {receiver_account}: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
