import asyncio
import logging
import os
import random
import re
from typing import Dict, Any, Optional, List

from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import Channel

from .proxy_helper import get_working_proxy_for_account, mark_proxy_dead
from .session_manager import SESSIONS_DIR, load_accounts_db

logger = logging.getLogger("pacocash.activator")

REQUIRED_BIO = "@winpaco — free case every day!"
TARGET_CHAT = "ChatPaco"
REQUIRED_CHANNELS = ["chatpaco", "pacocartel", "WinPacoLive", "w1paco", "inona4ka"]

CASUAL_PHRASES = [
    "ку всем", "привет народ", "как делишки?", "сегодня кто вывел?",
    "пако пушка", "кто в кости поднял?", "я пока по мелочи играю",
    "розыгрыш сегодня в 21:00 как обычно?", "удачи всем в конкурсе",
    "кто-то выводил на криптобота?", "моментально приходит?", "норм тема",
    "ждем розыгрыш", "всем профита", "сегодня удачный день",
    "а сколько в среднем вывод идет?", "минута где-то?", "ого быстро",
    "топчик", "кто сколько за день поднял?", "красава", "давай тащи",
    "жестко", "в рулетку кто играет?", "ставки чисто по фану",
    "главное не азартить сильно", "ну чисто для розыгрыша пишу",
    "51 смс набить недолго", "чат живой прям", "всем доброго вечера",
    "погнали", "плюс", "го", "у кого какой баланс?", "пако платит проверено",
    "хорош", "держите в курсе", "фарта", "увидимся на розыгрыше",
    "вечер в хату", "надеюсь сегодня повезет", "всем зеленых свечей",
    "пако бот крутой", "баланс капает потихоньку", "у кого сколько сообщений уже?",
    "на криптобот чеком выводят?", "давно в пако играете?", "радует что без задержек",
    "всем удачи", "завтра тоже будет розыгрыш?", "круто придумали с чатом",
    "надеюсь залутать приз", "чисто на расслабоне", "всем добра и профита",
    "плюсую", "согласен", "посмотрим вечером", "всем фарту"
]

async def get_chat_stats(client: TelegramClient, bot_entity) -> tuple[int, int]:
    """
    Returns (received_messages, paid_messages) from PacoCashBot u:pay:home menu.
    """
    try:
        await client.send_message(bot_entity, "/start")
        await asyncio.sleep(2.0)
        msgs = await client.get_messages(bot_entity, limit=3)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, 'data', None) == b'u:pay:home':
                            await m.click(data=b'u:pay:home')
                            await asyncio.sleep(2.5)
                            refreshed = await client.get_messages(bot_entity, ids=m.id)
                            recv = 0
                            paid = 0
                            for line in (refreshed.text or "").split('\n'):
                                if 'Сообщений получено:' in line:
                                    m_recv = re.search(r'\*\*([0-9]+)\*\*', line)
                                    if m_recv: recv = int(m_recv.group(1))
                                if 'Оплачено:' in line:
                                    m_paid = re.search(r'\*\*([0-9]+)\*\*', line)
                                    if m_paid: paid = int(m_paid.group(1))
                            return recv, paid
    except Exception as e:
        logger.debug(f"Error fetching stats: {e}")
    return 0, 0

async def ensure_bio_and_verification(client: TelegramClient, bot_entity) -> bool:
    """
    Ensures account has the required bio and is verified in PacoCashBot.
    """
    try:
        me = await client.get_me()
        full = await client.get_entity(me.id)
        # Note: full entity about may require GetFullUserRequest, but we can set it directly
        await client(UpdateProfileRequest(about=REQUIRED_BIO))
        await asyncio.sleep(1.0)

        # Check and click u:pay:bio in bot
        await client.send_message(bot_entity, "/start")
        await asyncio.sleep(2.0)
        msgs = await client.get_messages(bot_entity, limit=3)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, 'data', None) == b'u:pay:home':
                            await m.click(data=b'u:pay:home')
                            await asyncio.sleep(2.0)
                            break

        msgs = await client.get_messages(bot_entity, limit=2)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, 'data', None) == b'u:pay:bio':
                            await m.click(data=b'u:pay:bio')
                            await asyncio.sleep(2.0)
                            return True
        return True
    except Exception as e:
        logger.warning(f"Error ensuring bio: {e}")
        return False

async def ensure_joined_channels(client: TelegramClient):
    """Joins ChatPaco and required partner channels."""
    for ch in REQUIRED_CHANNELS:
        try:
            ent = await client.get_entity(ch)
            await client(JoinChannelRequest(ent))
            await asyncio.sleep(1.5)
        except Exception as e:
            # Already joined or restricted
            logger.debug(f"Join channel {ch}: {e}")

async def activate_child_account(
    session_name: str,
    cfg: dict,
    progress_cb=None
) -> Dict[str, Any]:
    """
    Brings a single child account to 51 paid messages in @ChatPaco:
    1. Connects with fresh proxy
    2. Sets bio & verifies with bot
    3. Joins @ChatPaco
    4. Sends messages with human-like delays until 51 paid messages are verified
    """
    s_path = os.path.join(SESSIONS_DIR, f"{session_name}.session")
    if not os.path.exists(s_path):
        return {"ok": False, "error": f"Session file not found: {s_path}"}

    accounts_db = load_accounts_db()
    meta = accounts_db.get(session_name, {})
    working_proxy = get_working_proxy_for_account(session_name, meta)
    tel_proxy = working_proxy.get("telethon") if isinstance(working_proxy, dict) else None

    client = TelegramClient(
        s_path,
        cfg["api_id"],
        cfg["api_hash"],
        proxy=tel_proxy,
        connection_retries=2,
        timeout=12.0
    )

    try:
        await asyncio.wait_for(client.connect(), timeout=12.0)
        if not await client.is_user_authorized():
            return {"ok": False, "error": "Account unauthorized"}

        bot = await client.get_entity("PacoCashBot")
        chat = await client.get_entity(TARGET_CHAT)

        # Run smart context-aware chatting with typing emulation & natural Russian dialogue
        from .smart_chatter import run_smart_chat_session
        res = await run_smart_chat_session(
            client=client,
            account_name=session_name,
            target_paid=51,
            progress_callback=progress_cb
        )
        await client.disconnect()
        return res

    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}
