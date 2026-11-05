import asyncio
import logging
import os
import re
import urllib.parse
from typing import Dict, Any, Optional, List

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.messages import StartBotRequest, RequestWebViewRequest
from telethon.tl.types import InputUser
from telethon.errors.common import AuthKeyNotFound

from .taskmask_verifier import verify_taskmask
from .wallet_generator import get_or_create_wallet_for_account

logger = logging.getLogger("pacocash.worker")

async def process_paco_account(
    account_name: str,
    session_file: str,
    api_id: int,
    api_hash: str,
    referral_code: str,
    channels: List[str],
    bio_text: str,
    meta: dict
) -> Dict[str, Any]:
    """
    Executes the full PacoCash onboarding and task verification for a single account:
    1. Connect via proxy
    2. Start bot with assigned referral code (pyramid or root)
    3. Join channels
    4. Set bio
    5. Accept 'Приписка' task
    6. Request webview & verify via TaskMask
    7. Extract account's own referral code (for pyramid expansion)
    8. Assign/generate dedicated TON wallet
    9. Read balance & hold
    10. Disconnect cleanly
    """
    dev = meta.get("device", {
        "device_model": "Desktop",
        "system_version": "Windows 11 x64",
        "app_version": "4.16.8 x64",
        "system_lang_code": "ru-RU",
        "lang_code": "ru"
    })
    proxy_info = meta.get("proxy", {})
    tel_proxy = proxy_info.get("telethon") if proxy_info else None
    http_proxy = proxy_info.get("http_url") if proxy_info else None
    user_agent = meta.get("user_agent")
    client_meta = meta.get("client_meta", {})

    client = TelegramClient(
        session_file,
        api_id,
        api_hash,
        proxy=tel_proxy,
        device_model=dev.get("device_model", "Desktop"),
        system_version=dev.get("system_version", "Windows 11 x64"),
        app_version=dev.get("app_version", "4.16.8 x64"),
        system_lang_code=dev.get("system_lang_code", "ru-RU"),
        lang_code=dev.get("lang_code", "ru"),
        connection_retries=2,
        retry_delay=1
    )

    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=15.0)
        except AuthKeyNotFound:
            return {"ok": False, "error": "AUTH_KEY_NOT_FOUND (сессия отключена Telegram)"}
        except asyncio.TimeoutError:
            return {"ok": False, "error": "PROXY_TIMEOUT (таймаут прокси - аккаунт ЖИВ)"}
        except Exception as e:
            return {"ok": False, "error": f"CONNECTION_ERROR ({e})"}

        if not await client.is_user_authorized():
            return {"ok": False, "error": "UNAUTHORIZED (сессия не авторизована)"}

        me = await client.get_me()
        user_label = f"{me.first_name or ''} {me.last_name or ''}".strip()
        phone = me.phone or "Unknown"

        # 1. Start Bot
        bot_entity = await client.get_input_entity("PacoCashBot")
        bot = InputUser(bot_entity.user_id, bot_entity.access_hash)

        # Check existing messages
        history = await client.get_messages("PacoCashBot", limit=5)
        already_started = any(m.id for m in history if m.text and "/start" in m.text)

        if not already_started:
            await client(StartBotRequest(
                bot=bot,
                peer=bot,
                start_param=referral_code
            ))
            await asyncio.sleep(2)

        # 2. Update Bio (disabled by user request)
        pass

        # 3. Join Channels
        joined_count = 0
        for ch in channels:
            try:
                ch_clean = ch.replace("https://t.me/", "").replace("@", "").strip()
                entity = await client.get_entity(ch_clean)
                await client(JoinChannelRequest(entity))
                joined_count += 1
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.warning(f"Failed to join channel {ch}: {e}")

        # 4. Accept 'Приписка' task (only if bio_text is configured)
        if bio_text:
            try:
                # Click Tasks
                msgs = await client.get_messages("PacoCashBot", limit=3)
                for m in msgs:
                    if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                        try:
                            await m.click(data=b'u:tl:av:0')
                            await asyncio.sleep(1.5)
                            break
                        except Exception:
                            pass

                # Click Pripiska
                msgs = await client.get_messages("PacoCashBot", limit=2)
                for m in msgs:
                    if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                        try:
                            await m.click(data=b'u:t:6')
                            await asyncio.sleep(1.5)
                            break
                        except Exception:
                            pass

                # Click Accept
                msgs = await client.get_messages("PacoCashBot", limit=2)
                for m in msgs:
                    if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                        try:
                            await m.click(data=b'u:acc:6')
                            await asyncio.sleep(1.5)
                            break
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"Error accepting pripiska task: {e}")

        # 5. Open Tasks and get Verify Button
        msgs = await client.get_messages("PacoCashBot", limit=3)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                try:
                    await m.click(data=b'u:tl:av:0')
                    await asyncio.sleep(1.5)
                    break
                except Exception:
                    pass

        msgs = await client.get_messages("PacoCashBot", limit=2)
        verify_btn = None
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for row in m.reply_markup.rows:
                    for b in row.buttons:
                        if "Проверить" in getattr(b, "text", "") and hasattr(b, "url"):
                            verify_btn = b
                            break
                    if verify_btn:
                        break
            if verify_btn:
                break

        verify_result = {"ok": False, "message": "Verify button not found"}
        if verify_btn:
            # Request Webview
            res = await client(RequestWebViewRequest(
                peer=bot,
                bot=bot,
                url=verify_btn.url,
                platform="tdesktop"
            ))

            parsed = urllib.parse.urlparse(res.url)
            frag = urllib.parse.parse_qs(parsed.fragment)
            init_data = frag.get("tgWebAppData", [None])[0]
            launch = frag.get("launch", [None])[0]
            if not launch:
                btn_parsed = urllib.parse.urlparse(verify_btn.url)
                launch = urllib.parse.parse_qs(btn_parsed.fragment).get("launch", [None])[0]

            if init_data and launch:
                verify_result = await verify_taskmask(
                    init_data=init_data,
                    launch=launch,
                    proxy_url=http_proxy,
                    user_agent=user_agent,
                    client_meta=client_meta
                )

        # 6. Extract Account's Own Referral Code
        own_ref_code = None
        try:
            # Go back to menu if needed
            msgs = await client.get_messages("PacoCashBot", limit=2)
            for m in msgs:
                if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                    try:
                        await m.click(data=b'u:menu')
                        await asyncio.sleep(1.5)
                        break
                    except Exception:
                        pass

            msgs = await client.get_messages("PacoCashBot", limit=2)
            for m in msgs:
                if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                    try:
                        await m.click(data=b'u:inv')
                        await asyncio.sleep(1.5)
                        break
                    except Exception:
                        pass

            msgs = await client.get_messages("PacoCashBot", limit=2)
            for m in msgs:
                match = re.search(r"t\.me/PacoCashBot\?start=([a-zA-Z0-9_\-]+)", m.text)
                if match:
                    own_ref_code = match.group(1)
                    break
        except Exception as e:
            logger.warning(f"Error fetching own referral link: {e}")

        # 7. Get or generate dedicated TON wallet
        wallet_info = get_or_create_wallet_for_account(account_name)

        # 8. Read Balance & Hold
        await asyncio.sleep(1)
        msgs = await client.get_messages("PacoCashBot", limit=3)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                try:
                    await m.click(data=b'u:bal:0')
                    await asyncio.sleep(1.5)
                    break
                except Exception:
                    pass

        msgs = await client.get_messages("PacoCashBot", limit=2)
        balance_text = msgs[0].text if msgs else ""

        available_val = 0.0
        held_val = 0.0
        pending_val = 0.0

        match_avail = re.search(r"Доступно к выводу:\s*\*\*?\$?([0-9\.]+)", balance_text)
        if match_avail:
            try: available_val = float(match_avail.group(1))
            except: pass

        match_held = re.search(r"Удерживается:\s*\$?([0-9\.]+)", balance_text)
        if match_held:
            try: held_val = float(match_held.group(1))
            except: pass

        match_pending = re.search(r"Ожидает проверки:\s*\$?([0-9\.]+)", balance_text)
        if match_pending:
            try: pending_val = float(match_pending.group(1))
            except: pass

        return {
            "ok": True,
            "user": user_label,
            "phone": phone,
            "parent_ref": referral_code,
            "own_ref_code": own_ref_code,
            "ton_address": wallet_info.get("address"),
            "joined_channels": joined_count,
            "verified": verify_result.get("ok", False),
            "verify_msg": verify_result.get("message", verify_result.get("error", "")),
            "available_balance": available_val,
            "held_balance": held_val,
            "pending_balance": pending_val,
            "balance_raw": balance_text
        }

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
