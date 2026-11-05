import asyncio
import json
import logging
import os
import random
import re
import sys
from datetime import datetime
from typing import Dict, Any, List

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("orchestrator.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("orchestrator")

from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import JoinChannelRequest

from core.proxy_helper import get_working_proxy_for_account
from core.session_manager import SESSIONS_DIR, load_accounts_db
from core.balance_syncer import fetch_live_bot_balance
from core.paco_withdraw import attempt_account_withdrawal
from core.cryptobot_claimer import claim_check_with_account

CONFIG_FILE = "config.json"
DATABASE_FILE = "database.json"
TARGET_CHAT = "ChatPaco"
REQUIRED_BIO = "@winpaco — free case every day!"
REQUIRED_CHANNELS = ["chatpaco", "pacocartel", "WinPacoLive", "w1paco", "inona4ka"]

def load_database() -> dict:
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_database(data: dict):
    with open(DATABASE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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

class ManagedChild:
    def __init__(self, session_name: str, parent_name: str, cfg: dict, accounts_db: dict):
        self.session_name = session_name
        self.parent_name = parent_name
        self.cfg = cfg
        self.accounts_db = accounts_db
        self.client: TelegramClient = None
        self.chat_entity = None
        self.bot_entity = None
        self.paid = 0
        self.received = 0
        self.setup_done = False
        self.is_done = False
        self.error = None

    async def connect_and_setup(self) -> bool:
        s_path = os.path.join(SESSIONS_DIR, f"{self.session_name}.session")
        if not os.path.exists(s_path):
            self.error = "No session file"
            return False

        meta = self.accounts_db.get(self.session_name, {})
        working_proxy = get_working_proxy_for_account(self.session_name, meta)
        tel_proxy = working_proxy.get("telethon") if isinstance(working_proxy, dict) else None

        self.client = TelegramClient(
            s_path[:-8],
            self.cfg["api_id"],
            self.cfg["api_hash"],
            proxy=tel_proxy,
            connection_retries=1,
            timeout=10.0
        )

        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                self.error = "Unauthorized"
                return False

            self.bot_entity = await self.client.get_entity("PacoCashBot")
            self.chat_entity = await self.client.get_entity(TARGET_CHAT)

            # Update bio
            try:
                await self.client(UpdateProfileRequest(about=REQUIRED_BIO))
            except Exception:
                pass

            # Join channels
            for ch in REQUIRED_CHANNELS:
                try:
                    ent = await self.client.get_entity(ch)
                    await self.client(JoinChannelRequest(ent))
                    await asyncio.sleep(1.0)
                except Exception:
                    pass

            # Verify bio in bot
            await self.verify_bio_in_bot()

            # Check stats
            await self.sync_stats()
            self.setup_done = True
            logger.info(f"[{self.session_name[:25]}] Setup OK. Initial paid: {self.paid}/51")
            if self.paid >= 51:
                self.is_done = True
            return True

        except Exception as e:
            self.error = str(e)
            logger.warning(f"[{self.session_name[:25]}] Setup failed: {e}")
            return False

    async def verify_bio_in_bot(self):
        try:
            await self.client.send_message(self.bot_entity, "/start")
            await asyncio.sleep(2.0)
            msgs = await self.client.get_messages(self.bot_entity, limit=3)
            for m in msgs:
                if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                    for r in m.reply_markup.rows:
                        for b in r.buttons:
                            if getattr(b, 'data', None) == b'u:pay:home':
                                await m.click(data=b'u:pay:home')
                                await asyncio.sleep(2.0)
                                break
            msgs = await self.client.get_messages(self.bot_entity, limit=2)
            for m in msgs:
                if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                    for r in m.reply_markup.rows:
                        for b in r.buttons:
                            if getattr(b, 'data', None) == b'u:pay:bio':
                                await m.click(data=b'u:pay:bio')
                                await asyncio.sleep(2.0)
                                return
        except Exception:
            pass

    async def sync_stats(self) -> int:
        try:
            await self.client.send_message(self.bot_entity, "/start")
            await asyncio.sleep(2.0)
            msgs = await self.client.get_messages(self.bot_entity, limit=3)
            for m in msgs:
                if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                    for r in m.reply_markup.rows:
                        for b in r.buttons:
                            if getattr(b, 'data', None) == b'u:pay:home':
                                await m.click(data=b'u:pay:home')
                                await asyncio.sleep(2.5)
                                refreshed = await self.client.get_messages(self.bot_entity, ids=m.id)
                                for line in (refreshed.text or "").split('\n'):
                                    if 'Оплачено:' in line:
                                        m_paid = re.search(r'\*\*([0-9]+)\*\*', line)
                                        if m_paid:
                                            self.paid = int(m_paid.group(1))
                                            return self.paid
        except Exception as e:
            logger.debug(f"Stats sync error: {e}")
        return self.paid

    async def send_one_message(self, text: str) -> bool:
        if self.is_done or not self.client:
            return False
        try:
            await self.client.send_message(self.chat_entity, text)
            self.paid += 1 # optimistic increment
            return True
        except Exception as e:
            err_str = str(e)
            if "forbidden" in err_str.lower() or "banned" in err_str.lower():
                logger.warning(f"[{self.session_name[:25]}] Muted/Restricted in chat: {e}")
                self.error = "Muted"
                self.is_done = True
            elif "slowmode" in err_str.lower():
                logger.debug(f"[{self.session_name[:25]}] Slowmode hit, waiting next round")
            else:
                logger.debug(f"[{self.session_name[:25]}] Send error: {e}")
            return False

    async def close(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass

async def withdraw_and_claim_parent(parent_name: str, cfg: dict, db: dict, accounts_db: dict):
    logger.info(f"===> Checking Parent: {parent_name} for withdrawal...")
    s_path = os.path.join(SESSIONS_DIR, f"{parent_name}.session")
    meta = accounts_db.get(parent_name, {})
    bal_res = await fetch_live_bot_balance(parent_name, s_path, cfg["api_id"], cfg["api_hash"], meta)
    logger.info(f"Parent balance check result: {bal_res}")

    avail = bal_res.get("available", 0.0) if bal_res.get("ok") else 0.0
    if parent_name in db:
        db[parent_name]["available"] = avail
        save_database(db)

    if avail >= 1.00:
        logger.info(f"PARENT {parent_name} HAS ${avail:.2f}! Triggering withdrawal...")
        tel_proxy = get_working_proxy_for_account(parent_name, meta).get("telethon")
        client = TelegramClient(s_path[:-8], cfg["api_id"], cfg["api_hash"], proxy=tel_proxy, timeout=10.0)
        await client.connect()
        w_res = await attempt_account_withdrawal(client, parent_name, meta=meta, amount=avail)
        await client.disconnect()

        if w_res.get("ok") and w_res.get("check_url"):
            check_url = w_res.get("check_url")
            receiver_name = cfg.get("receiver_account", "[RU] Xxxcalibur +79936124946 2025")
            logger.info(f"CHEQUE ISSUED: {check_url}! Claiming to {receiver_name}...")
            claim_res = await claim_check_with_account(check_url, receiver_account=receiver_name, cfg=cfg)
            if claim_res.get("ok"):
                logger.info(f"SUCCESSFULLY CLAIMED ${avail:.2f} USDT to {receiver_name}!")
            else:
                logger.warning(f"Claim failed: {claim_res.get('error')}")

            db[parent_name]["withdrawn"] = True
            db[parent_name]["check_url"] = check_url
            db[parent_name]["status"] = "ARCHIVED"
            save_database(db)
            return True
    return False

async def run_orchestrator(max_pool_size: int = 4):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    db = load_database()
    accounts_db = load_accounts_db()

    with open("targets_report.json", "r", encoding="utf-8") as f:
        targets = json.load(f)

    # Build queue of (child, parent)
    queue = []
    for t in targets:
        p = t["parent"]
        av = t["avail"]
        ac = t["alive_children"]
        if av + len(ac) * 0.5 >= 1.0:
            needed_cnt = int((1.0 - av + 0.49) // 0.5) if av < 1.0 else 0
            for c in ac[:needed_cnt]:
                queue.append((c, p))

    logger.info(f"Total children tasks in queue: {len(queue)}")
    pool: List[ManagedChild] = []
    queue_idx = 0
    phrase_idx = 0

    while pool or queue_idx < len(queue):
        # Fill pool up to max_pool_size
        while len(pool) < max_pool_size and queue_idx < len(queue):
            child_name, parent_name = queue[queue_idx]
            queue_idx += 1
            mc = ManagedChild(child_name, parent_name, cfg, accounts_db)
            ok = await mc.connect_and_setup()
            if ok and not mc.is_done:
                pool.append(mc)
            else:
                await mc.close()
                if mc.is_done:
                    await withdraw_and_claim_parent(parent_name, cfg, db, accounts_db)

        if not pool:
            break

        # Round-robin: each child in pool sends 1 message
        for mc in list(pool):
            if mc.is_done:
                continue

            phrase = CASUAL_PHRASES[phrase_idx % len(CASUAL_PHRASES)]
            phrase_idx += 1

            sent = await mc.send_one_message(phrase)
            if sent:
                logger.info(f"[{mc.session_name[:20]}] Sent msg (est: {mc.paid}/51): '{phrase[:25]}'")

            # Check every 10 messages or if reached 51
            if mc.paid % 10 == 0 or mc.paid >= 51:
                real_paid = await mc.sync_stats()
                logger.info(f"==> [{mc.session_name[:20]}] Verified stats: {real_paid}/51")
                if real_paid >= 51:
                    mc.is_done = True
                    logger.info(f"🏆 [{mc.session_name}] REACHED 51 MESSAGES!")
                    await mc.close()
                    pool.remove(mc)
                    # Trigger parent check and withdrawal!
                    await withdraw_and_claim_parent(mc.parent_name, cfg, db, accounts_db)

            # Delay between messages across different accounts in the pool
            # 16-20 seconds delay between consecutive messages in the chat
            inter_msg_delay = random.uniform(16.0, 20.0)
            await asyncio.sleep(inter_msg_delay)

        # Clean finished/failed from pool
        for mc in list(pool):
            if mc.is_done or mc.error:
                await mc.close()
                if mc in pool:
                    pool.remove(mc)
                if mc.paid >= 51:
                    await withdraw_and_claim_parent(mc.parent_name, cfg, db, accounts_db)

    logger.info("=== ORCHESTRATOR COMPLETED ALL QUEUED TASKS ===")

if __name__ == '__main__':
    asyncio.run(run_orchestrator(max_pool_size=4))
