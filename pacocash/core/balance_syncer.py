import asyncio
import logging
import re
from typing import Dict, Any, Optional

from telethon import TelegramClient, errors
from .proxy_helper import get_working_proxy_for_account, mark_proxy_dead

logger = logging.getLogger("pacocash.balance_syncer")

async def fetch_live_bot_balance(
    account_name: str,
    session_file: str,
    api_id: int,
    api_hash: str,
    meta: dict
) -> Dict[str, Any]:
    """
    Connects to Telegram via proxy, fetches the actual live balance from PacoCashBot:
    - Доступно к выводу ($)
    - Удерживается ($)
    - Ожидает проверки ($)
    Automatically catches proxy 407 / timeout errors, rotates a fresh proxy from RB_Autimatic,
    and retries cleanly without crashing Telethon's internal network loop.
    """
    dev = meta.get("device", {
        "device_model": "Desktop", "system_version": "Windows 11 x64",
        "app_version": "4.16.8 x64", "system_lang_code": "ru-RU", "lang_code": "ru"
    })

    last_error = ""
    for attempt in range(2):
        working_proxy = get_working_proxy_for_account(account_name, meta, force_rotate=(attempt > 0))
        tel_proxy = working_proxy.get("telethon") if isinstance(working_proxy, dict) else None

        client = TelegramClient(
            session_file,
            api_id,
            api_hash,
            proxy=tel_proxy,
            device_model=dev.get("device_model", "Desktop"),
            system_version=dev.get("system_version", "Windows 11 x64"),
            app_version=dev.get("app_version", "4.16.8 x64"),
            connection_retries=1,
            retry_delay=1,
            auto_reconnect=False,
            timeout=6.0
        )

        async def _do_fetch():
            await client.connect()
            if not await client.is_user_authorized():
                return {"ok": False, "is_dead": True, "error": "UNAUTHORIZED (Сессия слетела)"}

            # Resolve PacoCashBot entity safely
            try:
                bot_entity = await client.get_input_entity("PacoCashBot")
            except Exception:
                try:
                    bot_entity = await client.get_entity("PacoCashBot")
                except Exception as ent_err:
                    return {"ok": False, "is_dead": False, "error": f"Не удалось найти PacoCashBot: {ent_err}"}

            # Request balance
            await client.send_message(bot_entity, "💰 Баланс")
            await asyncio.sleep(1.5)

            msgs = await client.get_messages(bot_entity, limit=3)
            text = ""
            for m in msgs:
                if m.text and ("Доступно к выводу" in m.text or "Баланс" in m.text or "История" in m.text):
                    text = m.text
                    break
            if not text and msgs:
                text = msgs[0].text or ""

            avail = 0.0
            held = 0.0
            pending = 0.0

            match_avail = re.search(r"Доступно к выводу:\s*\*\*?\$?([0-9\.]+)", text)
            if match_avail:
                try: avail = float(match_avail.group(1))
                except: pass

            match_held = re.search(r"Удерживается:\s*\$?([0-9\.]+)", text)
            if match_held:
                try: held = float(match_held.group(1))
                except: pass

            match_pending = re.search(r"Ожидает проверки:\s*\$?([0-9\.]+)", text)
            if match_pending:
                try: pending = float(match_pending.group(1))
                except: pass

            return {
                "ok": True,
                "is_dead": False,
                "available": avail,
                "held": held,
                "pending": pending,
                "raw": text
            }

        try:
            return await asyncio.wait_for(_do_fetch(), timeout=12.0)
        except (errors.AuthKeyUnregisteredError, errors.UserDeactivatedError, errors.UserDeactivatedBanError, errors.SessionRevokedError, errors.SessionExpiredError) as dead_err:
            return {"ok": False, "is_dead": True, "error": f"Слетела сессия ({dead_err})"}
        except Exception as e:
            err_str = str(e)
            is_dead = any(s in err_str.lower() for s in ["unauthorized", "unregistered", "revoked", "deactivated", "auth key", "different ip addresses", "no longer be used"])
            if is_dead:
                return {"ok": False, "is_dead": True, "error": err_str}

            is_proxy_err = any(s in err_str.lower() for s in ["407", "proxy", "timeout", "timed out", "connection reset", "socks", "tunnel connection failed"])
            if is_proxy_err and attempt == 0:
                raw_p = working_proxy.get("raw") if isinstance(working_proxy, dict) else None
                if raw_p:
                    mark_proxy_dead(raw_p)
                logger.debug(f"[PROXY] Proxy error for {account_name} ({err_str}). Retrying with fresh proxy from RB_Autimatic...")
                continue

            last_error = err_str
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    return {"ok": False, "is_dead": False, "error": last_error or "Ошибка прокси"}
