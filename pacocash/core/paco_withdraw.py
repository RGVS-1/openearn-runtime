import asyncio
import logging
import re
import urllib.parse
from typing import Dict, Any, Optional

from telethon import TelegramClient
from telethon.tl.types import InputUser
from telethon.tl.functions.messages import RequestWebViewRequest

from .taskmask_verifier import verify_taskmask

logger = logging.getLogger("pacocash.withdraw")

async def attempt_account_withdrawal(
    client: TelegramClient,
    account_name: str,
    meta: Optional[dict] = None,
    amount: float = 1.0
) -> Dict[str, Any]:
    """
    Executes automated withdrawal for PacoCashBot:
    1. Requests fresh '💰 Баланс'
    2. Finds '💸 Вывод' KeyboardButtonWebView button
    3. Calls RequestWebViewRequest to obtain init_data and launch token
    4. Completes TaskMask anti-fraud verification
    5. Receives CryptoBot cheque link (https://t.me/CryptoBot?start=...)
    6. Returns check details
    """
    try:
        meta = meta or {}
        proxy_info = meta.get("proxy", {})
        http_proxy = proxy_info.get("http_url") if isinstance(proxy_info, dict) else None
        user_agent = meta.get("user_agent")
        client_meta = meta.get("client_meta", {})

        try:
            bot_ent = await client.get_input_entity("PacoCashBot")
            bot = InputUser(bot_ent.user_id, bot_ent.access_hash)
            # 1. Request fresh balance
            await client.send_message("PacoCashBot", "💰 Баланс")
        except Exception as peer_err:
            if "invalid Peer" in str(peer_err) or "frozen" in str(peer_err).lower() or "PeerUser" in str(peer_err):
                return {"ok": False, "status": "FROZEN", "error": "Аккаунт заморожен в Telegram (frozen)"}
            return {"ok": False, "error": f"Ошибка отправки команды боту: {peer_err}"}
        await asyncio.sleep(2.5)

        msgs = await client.get_messages("PacoCashBot", limit=2)
        bal_msg = msgs[0] if msgs else None
        if not bal_msg:
            return {"ok": False, "error": "Сообщение баланса не получено"}

        # Check if balance is insufficient
        text = bal_msg.text or ""
        if "Для вывода нужно минимум" in text:
            match_avail = re.search(r"Доступно к выводу:\s*\*\*?\$?([0-9\.]+)", text)
            avail_val = float(match_avail.group(1)) if match_avail else 0.0
            if avail_val < 1.00:
                return {
                    "ok": False,
                    "status": "INSUFFICIENT_FUNDS",
                    "error": f"Недостаточно средств: доступно ${avail_val:.2f} (минимум $1.00)"
                }

        # 2. Find withdraw webview button
        withdraw_btn = None
        if bal_msg.reply_markup and hasattr(bal_msg.reply_markup, 'rows'):
            for row in bal_msg.reply_markup.rows:
                for b in row.buttons:
                    if "💸" in getattr(b, "text", "") and hasattr(b, "url") and b.url:
                        withdraw_btn = b
                        break
                if withdraw_btn:
                    break

        if not withdraw_btn:
            return {"ok": False, "error": "Кнопка вывода (WebView) не найдена в сообщении баланса"}

        # 3. Request WebView
        web_view = await client(RequestWebViewRequest(
            peer=bot,
            bot=bot,
            url=withdraw_btn.url,
            platform="tdesktop",
            from_bot_menu=False
        ))

        full_url = web_view.url
        parsed = urllib.parse.urlparse(full_url)
        frag = urllib.parse.parse_qs(parsed.fragment)
        init_data = frag.get("tgWebAppData", [None])[0]
        launch = frag.get("launch", [None])[0]

        if not launch:
            btn_parsed = urllib.parse.urlparse(withdraw_btn.url)
            launch = urllib.parse.parse_qs(btn_parsed.fragment).get("launch", [None])[0]

        if not init_data or not launch:
            return {"ok": False, "error": "Не удалось извлечь init_data или launch токен"}

        # 4. Verify via TaskMask
        ver_res = await verify_taskmask(
            init_data=init_data,
            launch=launch,
            proxy_url=http_proxy,
            user_agent=user_agent,
            client_meta=client_meta
        )

        if not ver_res.get("ok"):
            return {
                "ok": False,
                "error": f"Верификация TaskMask не пройдена: {ver_res.get('error')}"
            }

        # 5. Wait for cheque message from bot
        await asyncio.sleep(4)
        latest_msgs = await client.get_messages("PacoCashBot", limit=3)
        check_url = None
        check_msg_text = ""

        for m in latest_msgs:
            m_text = m.text or ""
            # Search for CryptoBot cheque link
            match_check = re.search(r"(https://t\.me/CryptoBot\?start=[a-zA-Z0-9_\-]+)", m_text)
            if match_check:
                check_url = match_check.group(1)
                check_msg_text = m_text
                break
            # Also check buttons
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        b_url = getattr(b, "url", "") or ""
                        if "CryptoBot?start=" in b_url:
                            check_url = b_url
                            check_msg_text = m_text
                            break
                    if check_url:
                        break
            if check_url:
                break

        if check_url:
            return {
                "ok": True,
                "status": "CHECK_ISSUED",
                "check_url": check_url,
                "message": check_msg_text,
                "amount": amount
            }

        return {
            "ok": True,
            "status": "VERIFIED_PENDING",
            "message": "Верификация пройдена, ожидается чек в боте"
        }

    except Exception as e:
        logger.error(f"Error during withdrawal attempt: {e}")
        return {"ok": False, "error": str(e)}
