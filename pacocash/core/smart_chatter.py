import asyncio
import logging
import random
import re
import time
from typing import Dict, Any, Optional, List, Tuple

from telethon import TelegramClient
from telethon.errors import SlowModeWaitError, FloodWaitError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import Message

from .proxy_helper import get_working_proxy_for_account
from .session_manager import SESSIONS_DIR, load_accounts_db

logger = logging.getLogger("pacocash.smart_chatter")

REQUIRED_BIO = "@winpaco — free case every day!"
TARGET_CHAT = "ChatPaco"
REQUIRED_CHANNELS = ["chatpaco", "pacocartel", "WinPacoLive", "w1paco", "inona4ka"]

# Global history to prevent repetition across any accounts
_GLOBAL_USED_PHRASES: List[str] = []
_MAX_GLOBAL_HISTORY = 60

# --- Comprehensive bank of natural Russian conversational phrases ---

# 1. Reactions to dice games / duels / wins in WinPaco
REACTIONS_TO_WIN = [
    "красава, грац", "норм поднял", "хорош", "тащит сегодня прям",
    "плюс балик, поздравляю", "красиво сыграно", "фартит", "мощно",
    "грац", "чисто на опыте", "красавчик", "вот это фарт",
    "вовремя стопайся только", "хороший куш", "грац с победой",
    "на тоненького зашло", "жестко затащил", "топчик"
]

REACTIONS_TO_LOSS = [
    "бывает, отыграешь", "не тильтуй главное", "жесть конечно",
    "казик дело такое", "бывает че", "лучше перерыв сделать",
    "не расстраивайся", "отыграешься еще", "да уж, обидно",
    "на костях чисто рандом", "ну такое конечно", "аккуратнее со ставками"
]

# 2. Reactions to bonus / WinPaco bot commands
REACTIONS_TO_BONUS = [
    "тоже бонус забрал", "у меня еще кд висит", "раз в два часа же вроде?",
    "спс что напомнил, ща чекну", "забыл совсем про бонус", "пако щедрый сегодня",
    "у меня через час только откатит", "кд быстро летит", "надо тоже забрать пойти",
    "каждые 2 часа стабильно лутаю", "бонус мелочь а приятно"
]

# 3. Answers to common questions (cashout, rules, 51 msgs, cryptobot)
ANSWERS_PAYOUT = [
    "на криптобот чеком выводят", "от 1 бакса вроде вывод", "минуты 2-3 и чек в боте",
    "моментально почти приходит", "пако стабильно платит, проверено",
    "через вебвью верификацию проходишь и чек дают", "вчера выводил, все четко"
]

ANSWERS_GOAL_51 = [
    "51 смс надо для розыгрыша набить", "до 21:00 по мск итоги вроде",
    "потихоньку набивается если общаться", "в био обязательно приписку надо ставить",
    "половину уже набил где-то", "главное чтоб зачли в розыгрыш",
    "каждый день десятку разыгрывают", "надеюсь сегодня повезет в десятку попасть"
]

ANSWERS_GENERIC_Q = [
    "хз если честно", "не уверен, надо в правилах глянуть", "вроде да",
    "да так и есть", "не знаю даже", "наверное", "в закрепе должно быть написано",
    "по факту", "плюсую"
]

# 4. Casual banter, thoughts, and conversational glue
CASUAL_BANTER = [
    "ку всем кто в чате", "всем доброго времени", "как успехи у народа?",
    "живой чат сегодня прям", "вечер в хату", "посмотрим что на розыгрыше будет",
    "всем удачи сегодня", "фарта мужики", "главное без азарта жесткого",
    "чисто на расслабоне сижу", "да уж", "согласен полностью", "жиза",
    "было такое", "ну да", "посмотрим как пойдет", "по тихой общаемся",
    "нормально так", "все на месте", "плюс", "да", "ну как сказать",
    "время покажет", "поглядим", "движ идет", "норм тема",
    "всем зеленых свечей", "надеюсь сегодня повезет", "день неплохой сегодня",
    "главное не спешить", "в кости чисто по фану катать надо",
    "тоже тут сижу", "всем профита", "увидимся на итогах",
    "активчик хороший", "потихоньку двигаемся", "красота"
]

def _pick_unique_phrase(pool: List[str], local_history: List[str]) -> str:
    """Selects a phrase from the pool that hasn't been used recently globally or locally."""
    global _GLOBAL_USED_PHRASES
    candidates = [
        p for p in pool
        if p not in _GLOBAL_USED_PHRASES[-_MAX_GLOBAL_HISTORY:] and p not in local_history[-20:]
    ]
    if not candidates:
        candidates = [p for p in pool if p not in local_history[-10:]]
    if not candidates:
        candidates = pool

    choice = random.choice(candidates)
    _GLOBAL_USED_PHRASES.append(choice)
    if len(_GLOBAL_USED_PHRASES) > _MAX_GLOBAL_HISTORY * 2:
        _GLOBAL_USED_PHRASES = _GLOBAL_USED_PHRASES[-_MAX_GLOBAL_HISTORY:]
    return choice


def analyze_and_generate_reply(recent_messages: List[Message], local_history: List[str]) -> Tuple[str, Optional[int]]:
    """
    Analyzes recent chat messages from @ChatPaco and returns:
    (message_text, optional_reply_to_msg_id)
    """
    if not recent_messages:
        return _pick_unique_phrase(CASUAL_BANTER, local_history), None

    last_msg = recent_messages[0]
    last_text = (last_msg.text or "").strip()
    last_text_lower = last_text.lower()

    # 1. Check if the latest message was a game outcome from WinPaco
    for m in recent_messages[:3]:
        t = (m.text or "").lower()
        if "победитель:" in t or "результаты #" in t:
            if "выигрыш:" in t or "победитель" in t:
                # React to victory
                phrase = _pick_unique_phrase(REACTIONS_TO_WIN, local_history)
                return phrase, None
        elif "проиграл" in t or "поражение" in t:
            phrase = _pick_unique_phrase(REACTIONS_TO_LOSS, local_history)
            return phrase, None

    # 2. Check if users are talking about Bonus
    for m in recent_messages[:4]:
        t = (m.text or "").lower()
        if "бонус" in t or "кд" in t or "таймаут" in t:
            phrase = _pick_unique_phrase(REACTIONS_TO_BONUS, local_history)
            return phrase, None

    # 3. Check if someone asked a question in the last 2 messages
    if "?" in last_text or last_text_lower.startswith(("как ", "где ", "кто ", "сколько ", "когда ")):
        # Ignore if bot was asking
        sender = getattr(last_msg, "sender", None)
        sender_username = getattr(sender, "username", "") or ""
        if "bot" not in sender_username.lower():
            if any(k in last_text_lower for k in ["вывод", "криптобот", "чек", "бакс", "деньги", "вывести"]):
                phrase = _pick_unique_phrase(ANSWERS_PAYOUT, local_history)
                return phrase, last_msg.id if random.random() < 0.6 else None
            elif any(k in last_text_lower for k in ["51", "смс", "сообщени", "розыгрыш", "био", "приписк"]):
                phrase = _pick_unique_phrase(ANSWERS_GOAL_51, local_history)
                return phrase, last_msg.id if random.random() < 0.6 else None
            else:
                phrase = _pick_unique_phrase(ANSWERS_GENERIC_Q, local_history)
                return phrase, last_msg.id if random.random() < 0.4 else None

    # 4. Check for dice / gambling discussion
    for m in recent_messages[:3]:
        t = (m.text or "").lower()
        if any(k in t for k in ["куб", "кости", "дуэль", "ставка", "банк", "х2", "слил", "поднял"]):
            if any(k in t for k in ["поднял", "занес", "выиграл", "плюс"]):
                phrase = _pick_unique_phrase(REACTIONS_TO_WIN, local_history)
            elif any(k in t for k in ["слил", "минус", "проиграл", "ноль"]):
                phrase = _pick_unique_phrase(REACTIONS_TO_LOSS, local_history)
            else:
                phrase = _pick_unique_phrase(CASUAL_BANTER, local_history)
            return phrase, None

    # 5. Default natural Russian casual banter
    phrase = _pick_unique_phrase(CASUAL_BANTER, local_history)
    return phrase, None


async def get_chat_stats(client: TelegramClient, bot_entity) -> Tuple[int, int]:
    """Returns (received_messages, paid_messages) from PacoCashBot."""
    try:
        await client.send_message(bot_entity, "/start")
        await asyncio.sleep(2.0)
        msgs = await client.get_messages(bot_entity, limit=3)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, "rows"):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, "data", None) == b"u:pay:home":
                            await m.click(data=b"u:pay:home")
                            await asyncio.sleep(2.2)
                            refreshed = await client.get_messages(bot_entity, ids=m.id)
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


async def ensure_bio_and_verification(client: TelegramClient, bot_entity) -> bool:
    """Ensures account has the required bio and is verified in PacoCashBot."""
    try:
        await client(UpdateProfileRequest(about=REQUIRED_BIO))
        await asyncio.sleep(1.0)

        # Click u:pay:home then u:pay:bio in bot
        await client.send_message(bot_entity, "/start")
        await asyncio.sleep(2.0)
        msgs = await client.get_messages(bot_entity, limit=3)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, "rows"):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, "data", None) == b"u:pay:home":
                            await m.click(data=b"u:pay:home")
                            await asyncio.sleep(2.0)
                            break

        msgs = await client.get_messages(bot_entity, limit=2)
        for m in msgs:
            if m.reply_markup and hasattr(m.reply_markup, "rows"):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, "data", None) == b"u:pay:bio":
                            await m.click(data=b"u:pay:bio")
                            await asyncio.sleep(2.0)
                            return True
        return True
    except Exception as e:
        logger.warning(f"Error ensuring bio: {e}")
        return False


async def ensure_joined_channels(client: TelegramClient):
    """Joins ChatPaco and partner channels."""
    for ch in REQUIRED_CHANNELS:
        try:
            ent = await client.get_entity(ch)
            await client(JoinChannelRequest(ent))
            await asyncio.sleep(1.5)
        except Exception as e:
            logger.debug(f"Join channel {ch}: {e}")


async def run_smart_chat_session(
    client: TelegramClient,
    account_name: str,
    target_paid: int = 51,
    progress_callback=None
) -> Dict[str, Any]:
    """
    Executes intelligent, context-aware chatting in @ChatPaco:
    - Reads recent messages before each reply.
    - Understands duels, bonus, cashout, and user inquiries.
    - Sets 'typing' presence for 2-4 seconds.
    - Delays 22-42 seconds between messages (strictly respecting slowmode).
    - Prevents canned repetitive spam.
    - Automatically checks verified count in PacoCashBot and stops at target_paid.
    """
    bot = await client.get_entity("PacoCashBot")
    chat = await client.get_entity(TARGET_CHAT)

    await ensure_bio_and_verification(client, bot)
    await ensure_joined_channels(client)

    recv, paid = await get_chat_stats(client, bot)
    logger.info(f"[{account_name}] Initial stats: received={recv}, paid={paid}/{target_paid}")
    if progress_callback:
        progress_callback(account_name, paid, target_paid, f"Начальный баланс: {paid}/{target_paid} сообщений")

    if paid >= target_paid:
        return {"ok": True, "paid": paid, "already_done": True}

    local_history: List[str] = []
    messages_sent = 0
    consecutive_errors = 0

    while paid < target_paid:
        try:
            # 1. Fetch recent messages to understand context
            recent_msgs = await client.get_messages(chat, limit=12)

            # 2. Generate contextual reply
            reply_text, reply_to_id = analyze_and_generate_reply(recent_msgs, local_history)
            local_history.append(reply_text)

            # 3. Simulate human typing
            typing_duration = random.uniform(2.0, 4.2)
            async with client.action(chat, "typing"):
                await asyncio.sleep(typing_duration)

            # 4. Send message (with optional reply_to)
            if reply_to_id and random.random() < 0.5:
                await client.send_message(chat, reply_text, reply_to=reply_to_id)
            else:
                await client.send_message(chat, reply_text)

            messages_sent += 1
            consecutive_errors = 0
            logger.info(f"[{account_name}] Sent #{messages_sent}: '{reply_text}' (progress approx {paid + messages_sent}/{target_paid})")

            # 5. Delay before next message (22-42s, safe and human-like)
            delay = random.uniform(22.0, 42.0)
            await asyncio.sleep(delay)

            # 6. Verify stats with bot every 7 messages or when approaching goal
            if messages_sent % 7 == 0 or (paid + messages_sent) >= target_paid:
                r, p = await get_chat_stats(client, bot)
                if p > paid:
                    paid = p
                logger.info(f"[{account_name}] Verified stats: {paid}/{target_paid} paid messages")
                if progress_callback:
                    progress_callback(account_name, paid, target_paid, f"Оплачено в боте: {paid}/{target_paid}")

                if paid >= target_paid:
                    break

        except SlowModeWaitError as slow_err:
            wait_s = slow_err.seconds or 10
            logger.warning(f"[{account_name}] Slowmode hit: sleeping {wait_s + 3}s")
            await asyncio.sleep(wait_s + 3)
        except FloodWaitError as flood_err:
            wait_s = flood_err.seconds or 30
            logger.warning(f"[{account_name}] Flood wait: sleeping {wait_s + 5}s")
            await asyncio.sleep(wait_s + 5)
        except Exception as e:
            err_str = str(e).lower()
            consecutive_errors += 1
            logger.error(f"[{account_name}] Chat error: {e}")
            if "banned" in err_str or "restricted" in err_str or "rights" in err_str:
                return {"ok": False, "error": f"Chat restricted: {e}", "paid": paid}
            if consecutive_errors >= 5:
                return {"ok": False, "error": f"Too many consecutive errors: {e}", "paid": paid}
            await asyncio.sleep(10)

    # Final verification
    recv, paid = await get_chat_stats(client, bot)
    return {
        "ok": paid >= target_paid,
        "paid": paid,
        "received": recv,
        "messages_sent": messages_sent
    }
