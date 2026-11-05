import asyncio
import logging
import random
import re
import time
from typing import Dict, Any, Optional, List, Tuple

from telethon import TelegramClient
from telethon.errors import (
    SlowModeWaitError,
    FloodWaitError,
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    ChannelPrivateError
)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import Message

from .proxy_helper import get_working_proxy_for_account
from .session_manager import SESSIONS_DIR, load_accounts_db

logger = logging.getLogger("pacocash.smart_chatter")

REQUIRED_BIO = "@winpaco — free case every day!"
TARGET_CHAT = "ChatPaco"
REQUIRED_CHANNELS = ["chatpaco", "pacocartel", "WinPacoLive", "w1paco", "inona4ka"]

async def safe_get_entity(client: TelegramClient, entity_name: str):
    try:
        from telethon.tl.functions.contacts import ResolveUsernameRequest
        clean = entity_name.lstrip('@')
        resolved = await client(ResolveUsernameRequest(clean))
        if resolved.chats:
            return resolved.chats[0]
        if resolved.users:
            return resolved.users[0]
    except Exception:
        pass
    try:
        return await client.get_entity(entity_name)
    except Exception as e:
        logger.warning(f"safe_get_entity {entity_name}: {e}")
        return entity_name


# Multilingual clean signals across English, German, Russian, Spanish
CLEAN_SPAMBOT_SIGNALS = [
    # English
    "good news", "no limits", "free as a bird", "free to chat", "no restrictions",
    # German (frequent when running on EU/Frankfurt servers)
    "gute nachrichten", "keine einschränkungen", "frei wie ein vogel", "keine beschränkungen",
    # Russian
    "отличные новости", "нет ограничений", "не наложено никаких ограничений",
    "свободен от каких-либо ограничений", "свободны как птица", "нет никаких ограничений",
    "ограничений нет",
    # Spanish
    "buenas noticias", "no tiene limitaciones", "libre como un pájaro", "sin restricciones",
]

async def auto_appeal_spambot(client: TelegramClient, bot) -> bool:
    """Attempts to automatically submit an appeal through SpamBot dialogue."""
    try:
        # Step 1: Look for "This is a mistake" button
        msgs = await client.get_messages(bot, limit=3)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        b_text = getattr(b, 'text', '')
                        if any(w in b_text.lower() for w in ["mistake", "ошибка", "fehler"]):
                            logger.info(f"SpamBot appeal step 1: clicking '{b_text}'")
                            await client.send_message(bot, b_text)
                            await asyncio.sleep(2.5)
                            break

        # Step 2: Confirmation "Yes, submit complaint" / "Yes" / "Да"
        msgs = await client.get_messages(bot, limit=2)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        b_text = getattr(b, 'text', '')
                        if b_text.strip().lower() in ["yes", "да", "ja"]:
                            logger.info(f"SpamBot appeal step 2: clicking '{b_text}'")
                            await client.send_message(bot, b_text)
                            await asyncio.sleep(2.5)
                            break

        # Step 3: "No! Never did that!" / "Нет, никогда"
        msgs = await client.get_messages(bot, limit=2)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        b_text = getattr(b, 'text', '')
                        if any(w in b_text.lower() for w in ["never", "никогда", "nie", "нет!"]):
                            logger.info(f"SpamBot appeal step 3: clicking '{b_text}'")
                            await client.send_message(bot, b_text)
                            await asyncio.sleep(2.5)
                            break

        # Step 4: Send natural appeal text
        appeal_msg = "Здравствуйте! Мой аккаунт был ограничен ошибочно. Я не отправлял спам или рекламу незнакомым людям. Пожалуйста, снимите ограничения."
        await client.send_message(bot, appeal_msg)
        await asyncio.sleep(2.0)
        logger.info("SpamBot appeal successfully submitted!")
        return True
    except Exception as e:
        logger.warning(f"Error during SpamBot appeal: {e}")
        return False

async def is_account_spamblocked(client: TelegramClient) -> Tuple[bool, str]:
    """Checks if account is restricted by Telegram's SpamBot (multilingual aware with auto-appeal)."""
    try:
        bot = await safe_get_entity(client, "SpamBot")
        await client.send_message(bot, "/start")
        await asyncio.sleep(2.5)
        msgs = await client.get_messages(bot, limit=2)
        txt = " ".join((m.text or "") for m in msgs).lower()
        if any(sig in txt for sig in CLEAN_SPAMBOT_SIGNALS):
            return False, "CLEAN"
            
        logger.warning(f"Account appears restricted by SpamBot. Text snippet: {txt[:100]}. Attempting auto-appeal...")
        appealed = await auto_appeal_spambot(client, bot)
        status = "SPAMBLOCK_APPEALED" if appealed else "SPAMBLOCK"
        return True, status
    except Exception as e:
        logger.warning(f"Error checking SpamBot: {e}")
        return False, f"UNKNOWN: {e}"

# Global history to prevent repetition across accounts
_GLOBAL_USED_PHRASES: List[str] = []
_MAX_GLOBAL_HISTORY = 60

# --- Clean, 100% natural, unobtrusive phrases matching @ChatPaco gambling/dice environment ---
# NO mentions of 51, sms, messages, bio, cryptobot, cheque, webview, payout or rules!

DICE_COMMANDS = [
    "Чет 1", "Нечет 1", "Б 1", "М 1", "Чет", "Нечет", "Б", "М",
    "Чет 0.5", "Нечет 0.5", "Б 0.5", "М 0.5", "Т 1", "К 1", "Чет 2",
    "Нечет 2", "Б 2", "М 2", "Дабл 1", "Чет 0.3", "Б 0.3"
]

GAMBLING_REACTIONS = [
    "красава", "норм зашло", "грац", "бывает че", "да уж", "плюс",
    "жесть конечно", "хорош", "чисто рандом", "топчик", "ахах", "красиво",
    "не тильтуй главное", "фартит сегодня", "вовремя стопайся", "красавчик"
]

def _pick_unique_phrase(pool: List[str], local_history: List[str]) -> str:
    """Selects a phrase from the pool that hasn't been used recently globally or locally."""
    global _GLOBAL_USED_PHRASES
    candidates = [
        p for p in pool
        if p not in _GLOBAL_USED_PHRASES[-_MAX_GLOBAL_HISTORY:] and p not in local_history[-15:]
    ]
    if not candidates:
        candidates = [p for p in pool if p not in local_history[-8:]]
    if not candidates:
        candidates = pool

    choice = random.choice(candidates)
    _GLOBAL_USED_PHRASES.append(choice)
    if len(_GLOBAL_USED_PHRASES) > _MAX_GLOBAL_HISTORY * 2:
        _GLOBAL_USED_PHRASES = _GLOBAL_USED_PHRASES[-_MAX_GLOBAL_HISTORY:]
    return choice


def analyze_and_generate_reply(recent_messages: List[Message], local_history: List[str]) -> Tuple[str, Optional[int]]:
    """
    Analyzes recent chat messages from @ChatPaco and returns a 100% natural gambling/dice phrase or bet.
    75% of messages are natural dice bets ('Чет 1', 'Б 1', 'М 1', etc.) which blend in seamlessly.
    25% are short realistic player reactions ('красава', 'норм зашло', 'бывает че').
    """
    # 75% of the time, post a realistic dice bet command
    if random.random() < 0.75:
        return _pick_unique_phrase(DICE_COMMANDS, local_history), None

    # 25% of the time, post a short gambling reaction
    return _pick_unique_phrase(GAMBLING_REACTIONS, local_history), None


async def get_chat_stats(client: TelegramClient, bot_entity=None) -> Tuple[int, int]:
    """Returns (received_messages, paid_messages) from PacoCashBot."""
    try:
        bot = await safe_get_entity(client, "PacoCashBot")
        await client.send_message(bot, "/start")
        await asyncio.sleep(2.0)
        msgs = await client.get_messages(bot, limit=3)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, "rows"):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, "data", None) == b"u:pay:home":
                            await m.click(data=b"u:pay:home")
                            await asyncio.sleep(2.5)
                            refreshed = await client.get_messages(bot, ids=m.id)
                            recv = 0
                            paid = 0
                            for line in (refreshed.text or "").split("\n"):
                                if "Сообщений получено:" in line:
                                    m_recv = re.search(r"\*\*([0-9]+)\*\*", line)
                                    if m_recv:
                                        recv = int(m_recv.group(1))
                                if "Оплачено:" in line:
                                    m_paid = re.search(r"\*\*([0-9]+)\*\*", line)
                                    if m_paid:
                                        paid = int(m_paid.group(1))
                            return recv, paid
    except Exception as e:
        logger.debug(f"Error fetching stats: {e}")
    return 0, 0


async def ensure_joined_channels(client: TelegramClient):
    """Joins ChatPaco and partner channels before bot verification."""
    for ch in REQUIRED_CHANNELS:
        try:
            ent = await safe_get_entity(client, ch)
            res = await client(JoinChannelRequest(ent))
            logger.info(f"Join channel {ch} SUCCESS: {type(res).__name__}")
            await asyncio.sleep(1.8)
        except Exception as e:
            logger.info(f"Join channel {ch} result: {type(e).__name__}: {e}")


async def ensure_bio_and_verification(client: TelegramClient, bot_entity=None) -> bool:
    """
    Ensures account has the required bio AND verifies both Bio and Channels in PacoCashBot.
    1. Set profile about = @winpaco — free case every day!
    2. Click u:pay:home in bot
    3. Click u:pay:bio (verify bio)
    4. Click u:pay:chats (verify partner channels)
    """
    try:
        # 1. Update Bio
        await client(UpdateProfileRequest(about=REQUIRED_BIO))
        logger.info(f"Updated bio to: '{REQUIRED_BIO}'")
        await asyncio.sleep(1.5)

        bot = await safe_get_entity(client, "PacoCashBot")
        await client.send_message(bot, "/start")
        await asyncio.sleep(2.0)

        # 2. Open pay home menu
        msgs = await client.get_messages(bot, limit=3)
        home_clicked = False
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, "rows"):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, "data", None) == b"u:pay:home":
                            await m.click(data=b"u:pay:home")
                            await asyncio.sleep(2.5)
                            home_clicked = True
                            break
                    if home_clicked:
                        break
            if home_clicked:
                break

        # 3. Click u:pay:bio
        msgs_after_home = await client.get_messages(bot, limit=3)
        for m in msgs_after_home:
            if m.reply_markup and hasattr(m.reply_markup, "rows"):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, "data", None) == b"u:pay:bio":
                            logger.info("Clicking u:pay:bio in bot...")
                            await m.click(data=b"u:pay:bio")
                            await asyncio.sleep(2.5)
                            break

        # 4. Click u:pay:chats (verify channel subscriptions)
        msgs_chats = await client.get_messages(bot, limit=3)
        for m in msgs_chats:
            if m.reply_markup and hasattr(m.reply_markup, "rows"):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, "data", None) == b"u:pay:chats":
                            logger.info("Clicking u:pay:chats in bot...")
                            await m.click(data=b"u:pay:chats")
                            await asyncio.sleep(2.5)
                            break

        logger.info("Bio and channels verification sequence completed.")
        return True
    except Exception as e:
        logger.warning(f"Error ensuring bio/verification: {e}")
        return False


async def run_smart_chat_session(
    client: TelegramClient,
    account_name: str,
    target_paid: int = 51,
    progress_callback=None
) -> Dict[str, Any]:
    """
    Executes intelligent, safe, natural chatting in @ChatPaco:
    - Joins channels first.
    - Ensures bio and confirms both bio and channels in PacoCashBot.
    - Sets 'typing' presence for 2.5-4.5 seconds.
    - Delays 35-65 seconds between messages (safe and human-like).
    - Sends directly to chat without replying to other users/bots.
    - Uses only natural gambling/dice chatter.
    - Automatically checks verified count in PacoCashBot and stops at target_paid.
    """
    bot = await safe_get_entity(client, "PacoCashBot")

    # 1. Join channels first, then verify with bot
    await ensure_joined_channels(client)
    await ensure_bio_and_verification(client, bot)

    # 2. Get chat entity AFTER joining
    chat = await safe_get_entity(client, TARGET_CHAT)

    recv, paid = await get_chat_stats(client, bot)
    current_count = max(recv, paid)
    logger.info(f"[{account_name}] Initial stats: received={recv}, paid={paid} (effective={current_count}/{target_paid})")
    if progress_callback:
        progress_callback(account_name, current_count, target_paid, f"Начальный баланс: {current_count}/{target_paid} сообщений")

    if current_count >= target_paid:
        return {"ok": True, "paid": current_count, "already_done": True}

    local_history: List[str] = []
    messages_sent = 0
    consecutive_errors = 0

    while current_count < target_paid:
        try:
            # 0. Check connection and auto-reconnect if needed
            if not client.is_connected():
                logger.info(f"[{account_name}] Client disconnected, reconnecting to Telegram...")
                try:
                    await client.connect()
                    logger.info(f"[{account_name}] Reconnected successfully!")
                except Exception as rec_err:
                    logger.warning(f"[{account_name}] Reconnection failed: {rec_err}")
                    consecutive_errors += 1
                    await asyncio.sleep(10)
                    continue

            # 1. Fetch recent messages for ambient context safely
            recent_msgs = []
            try:
                recent_msgs = await client.get_messages(chat, limit=6)
            except Exception as read_err:
                logger.debug(f"[{account_name}] Note: Ambient messages unread: {read_err}")

            # 2. Pick natural contextual phrase
            reply_text, _ = analyze_and_generate_reply(recent_msgs, local_history)
            local_history.append(reply_text)

            # 3. Simulate human typing
            typing_duration = random.uniform(2.5, 4.5)
            try:
                async with client.action(chat, "typing"):
                    await asyncio.sleep(typing_duration)
            except Exception:
                await asyncio.sleep(typing_duration)

            # 4. Send message cleanly directly to the chat
            await client.send_message(chat, reply_text)

            messages_sent += 1
            consecutive_errors = 0
            current_count = max(current_count + 1, recv, paid)
            logger.info(f"[{account_name}] Sent #{messages_sent}: '{reply_text}' (progress approx {current_count}/{target_paid})")

            # 5. Delay before next message (35-65s, safe, natural, and relaxed)
            delay = random.uniform(35.0, 65.0)
            await asyncio.sleep(delay)

            # 6. Verify stats with bot every 5 messages or when approaching goal
            if messages_sent % 5 == 0 or current_count >= target_paid:
                r, p = await get_chat_stats(client, bot)
                recv = max(recv, r)
                paid = max(paid, p)
                current_count = max(current_count, recv, paid)
                logger.info(f"[{account_name}] Verified stats in bot: recv={recv}, paid={paid} (effective={current_count}/{target_paid})")
                if progress_callback:
                    progress_callback(account_name, current_count, target_paid, f"Сообщений в боте: {current_count}/{target_paid}")

                if current_count >= target_paid:
                    break

        except SlowModeWaitError as slow_err:
            wait_s = slow_err.seconds or 15
            logger.warning(f"[{account_name}] Slowmode hit: sleeping {wait_s + 5}s")
            await asyncio.sleep(wait_s + 5)
        except FloodWaitError as flood_err:
            wait_s = flood_err.seconds or 35
            logger.warning(f"[{account_name}] Flood wait: sleeping {wait_s + 10}s")
            await asyncio.sleep(wait_s + 10)
        except (ChatWriteForbiddenError, UserBannedInChannelError, ChannelPrivateError) as ban_err:
            logger.warning(f"[{account_name}] Account is forbidden or banned from chat: {ban_err}")
            return {"ok": False, "error": f"Chat restricted: {ban_err}", "paid": current_count}
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"[{account_name}] Chat error: {type(e).__name__}: {e}")
            if not client.is_connected() or "disconnected" in str(e).lower():
                try:
                    await client.connect()
                except Exception:
                    pass
            if consecutive_errors >= 8:
                return {"ok": False, "error": f"Too many consecutive errors: {e}", "paid": current_count}
            await asyncio.sleep(12)

    # Final verification
    recv, paid = await get_chat_stats(client, bot)
    final_count = max(recv, paid, current_count)
    return {
        "ok": final_count >= target_paid,
        "paid": final_count,
        "received": recv,
        "messages_sent": messages_sent
    }
