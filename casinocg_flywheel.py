import asyncio
import io
import json
import logging
import os
import random
import re
import sqlite3
import string
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests
from telethon import TelegramClient
from telethon.tl.functions.account import (
    GetPasswordRequest,
    SetPrivacyRequest,
    UpdateProfileRequest,
    UpdateUsernameRequest,
)
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import (
    GetBotCallbackAnswerRequest,
    GetHistoryRequest,
    RequestMainWebViewRequest,
)
from telethon.tl.types import (
    InputPrivacyKeyAddedByPhone,
    InputPrivacyKeyPhoneNumber,
    InputPrivacyValueAllowContacts,
    InputPrivacyValueDisallowAll,
)

logger = logging.getLogger("casinocg_flywheel")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "casinocg_state.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
SESSIONS_DIR = os.path.join(BASE_DIR, "cg_sessions")
MAIN_SESSION = os.path.join(BASE_DIR, "sessions", "[RU] Xxxcalibur +79936124946 2025.session")

os.makedirs(SESSIONS_DIR, exist_ok=True)

# DC IP Addresses for Telethon SQLite session creation
DC_IPS = {
    1: "149.154.175.53",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130"
}

def load_json(path: str, default: dict) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read {path}: {e}")
    return default.copy()

def save_json(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    if os.path.exists(path):
        os.remove(path)
    os.rename(tmp, path)

def load_flywheel_state() -> dict:
    default = {
        "cycle_count": 1,
        "current_scale": 1,
        "total_withdrawn_usd": 0.98,
        "total_cheques_collected": 0,
        "pending_withdrawals": [
            {
                "account": "prem_270189066",
                "session_file": os.path.join(SESSIONS_DIR, "prem_270189066.session"),
                "request_id": 334,
                "job_id": 2481,
                "amount": 0.98,
                "coin": "USDT",
                "method": "xrocket",
                "status": "pending",
                "created_at": "2026-11-04T08:43:35Z"
            }
        ],
        "accounts_to_sell": [],
        "sold_accounts": [
            {"id": 270339266, "price": 0.60, "phone": "+12494427798", "buyer": "pharita"},
            {"id": 270339283, "price": 0.60, "phone": "+12496438185", "buyer": "xelenkagururuk"},
            {"id": 270339302, "price": 0.60, "phone": "+12496456173", "buyer": "pharita"},
            {"id": 270339330, "price": 0.60, "phone": "+12496456880", "buyer": "oolebyv2"},
            {"id": 270339354, "price": 0.60, "phone": "+12496467531", "buyer": "cil0v0"},
            {"id": 270339392, "price": 0.60, "phone": "+12496477010", "buyer": "xelenkagururuk"},
            {"id": 270339402, "price": 0.60, "phone": "+12496488774", "buyer": "Topcik213"},
            {"id": 270339419, "price": 0.59, "phone": "+15485406931", "buyer": None}
        ],
        "logs": []
    }
    return load_json(STATE_FILE, default)

def log_event(state: dict, msg: str):
    logger.info(msg)
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    state.setdefault("logs", []).append(f"[{ts}] {msg}")
    state["logs"] = state["logs"][-100:]
    save_json(STATE_FILE, state)

class LZTClient:
    def __init__(self, token: str, proxy: Optional[dict] = None):
        self.token = token
        self.proxy = proxy
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        self.base_url = "https://api.lzt.market"

    def get_balances(self) -> dict:
        try:
            r = requests.get(f"{self.base_url}/me", headers=self.headers, proxies=self.proxy, timeout=10)
            if r.status_code == 200:
                u = r.json().get("user", {})
                return {
                    "balance": float(u.get("balance", 0.0)),
                    "hold": float(u.get("hold", 0.0)),
                    "balances": u.get("balances", [])
                }
        except Exception as e:
            logger.warning(f"LZT get_balances error: {e}")
        return {"balance": 0.0, "hold": 0.0, "balances": []}

    def search_premium_accounts(self, max_price: float = 0.68, limit: int = 10) -> List[dict]:
        try:
            params = {
                "premium": "yes",
                "pmax": max_price,
                "currency": "usd",
                "order_by": "price_to_up"
            }
            r = requests.get(f"{self.base_url}/telegram", headers=self.headers, params=params, proxies=self.proxy, timeout=12)
            if r.status_code == 200:
                items = r.json().get("items", [])
                clean = []
                for it in items:
                    spam = it.get("telegram_spamblock")
                    if spam is None or spam == 0 or spam == "0":
                        clean.append(it)
                return clean[:limit]
        except Exception as e:
            logger.warning(f"LZT search error: {e}")
        return []

    def fast_buy(self, item_id: int, price: float, balance_id: Optional[int] = 21026) -> Tuple[bool, dict]:
        try:
            payload = {"price": price}
            if balance_id:
                payload["balance_id"] = balance_id
            r = requests.post(f"{self.base_url}/{item_id}/fast-buy", headers=self.headers, json=payload, proxies=self.proxy, timeout=25)
            if r.status_code in [200, 201]:
                return True, r.json().get("item", {})
            else:
                logger.warning(f"LZT buy failed #{item_id}: {r.status_code} {r.text[:150]}")
        except Exception as e:
            logger.error(f"LZT buy exception #{item_id}: {e}")
        return False, {}

    def fast_sell(self, auth_key_hex: str, dc_id: int, price: float = 0.60, title: str = "+1 | Канада Телеграмм аккаунт | Отлежка | Чистый") -> Tuple[bool, str]:
        try:
            payload = {
                "price": price,
                "category_id": 24,
                "item_origin": "autoreg",
                "currency": "usd",
                "title": title,
                "description": "Чистый канадский Telegram аккаунт (+1). Отлежка, без спамблока.",
                "login": auth_key_hex,
                "password": str(dc_id),
                "tag_id": [3],
                "allow_ask_discount": True,
                "random_proxy": True,
                "extra": {"checkSpam": True}
            }
            r = requests.post(f"{self.base_url}/item/fast-sell", headers=self.headers, json=payload, proxies=self.proxy, timeout=25)
            if r.status_code in [200, 201]:
                data = r.json()
                item_id = data.get("item", {}).get("item_id")
                return True, f"https://lzt.market/{item_id}/"
            else:
                return False, r.text[:150]
        except Exception as e:
            return False, str(e)

def create_session_from_auth_key(session_path: str, auth_key_hex: str, dc_id: int = 1):
    auth_key_bytes = bytes.fromhex(auth_key_hex)
    server_addr = DC_IPS.get(dc_id, "149.154.175.53")
    if os.path.exists(session_path):
        os.remove(session_path)

    conn = sqlite3.connect(session_path)
    c = conn.cursor()
    c.execute("CREATE TABLE version (version integer)")
    c.execute("INSERT INTO version VALUES (7)")
    c.execute("CREATE TABLE sessions (dc_id integer primary key, server_address text, port integer, auth_key blob, takeout_id integer)")
    c.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)", (dc_id, server_addr, 443, auth_key_bytes, None))
    c.execute("CREATE TABLE entities (id integer primary key, hash integer not null, username text, phone integer, name text, date integer)")
    c.execute("CREATE TABLE sent_files (md5_digest blob, file_size integer, type integer, id integer, hash integer, primary key(md5_digest, file_size, type))")
    c.execute("CREATE TABLE update_state (id integer primary key, pts integer, qts integer, date integer, seq integer)")
    conn.commit()
    conn.close()

class CasinoCGWorker:
    def __init__(self, session_path: str, api_id: int = 2040, api_hash: str = "b18441a1ff607e10a989891a5462e627", proxy: Optional[tuple] = None):
        self.session_path = session_path
        self.api_id = api_id
        self.api_hash = api_hash
        self.proxy = proxy
        self.web_base = "https://crypto-game.sbs"
        self.bot_username = "casinocgbot"

    async def execute_cg_cycle(self) -> dict:
        """Executes full CasinoCG flow: hide phone -> tag -> solve captcha -> spin wheel -> wager -> withdraw"""
        res = {
            "success": False,
            "prize": 0.0,
            "balance": 0.0,
            "withdrawn": False,
            "request_id": None,
            "error": None
        }

        client = TelegramClient(self.session_path, self.api_id, self.api_hash, proxy=self.proxy)
        sess = requests.Session()

        try:
            await client.connect()
            if not await client.is_user_authorized():
                res["error"] = "Unauthorized"
                return res

            me = await client.get_me()
            # 1. Hide phone in Telegram Privacy
            try:
                await client(SetPrivacyRequest(key=InputPrivacyKeyPhoneNumber(), rules=[InputPrivacyValueDisallowAll()]))
                await client(SetPrivacyRequest(key=InputPrivacyKeyAddedByPhone(), rules=[InputPrivacyValueAllowContacts()]))
            except Exception:
                pass

            # 2. Tag @casinocgbot prefix in first_name
            orig_first = me.first_name or "User"
            orig_last = me.last_name or ""
            if "@casinocgbot" not in orig_first.lower():
                new_first = f"@casinocgbot {orig_first}".strip()[:64]
                try:
                    await client(UpdateProfileRequest(first_name=new_first, last_name=orig_last[:64]))
                except Exception:
                    pass

            bot = await client.get_input_entity(self.bot_username)
            await client.send_message(bot, "/start")
            await asyncio.sleep(2.0)

            # 3. Join required channels & solve captcha
            hist = await client(GetHistoryRequest(peer=bot, offset_id=0, offset_date=None, add_offset=0, limit=10, max_id=0, min_id=0, hash=0))
            for msg in hist.messages:
                if msg.reply_markup and hasattr(msg.reply_markup, 'rows'):
                    for row in msg.reply_markup.rows:
                        for btn in row.buttons:
                            if getattr(btn, 'data', None) == b'check_subscription':
                                for ch in ['budka_ccbets', 'chat_cgbet']:
                                    try:
                                        ch_ent = await client.get_input_entity(ch)
                                        await client(JoinChannelRequest(ch_ent))
                                    except Exception:
                                        pass
                                try:
                                    await client(GetBotCallbackAnswerRequest(peer=bot, msg_id=msg.id, data=b'check_subscription'))
                                except Exception:
                                    pass
                            elif getattr(btn, 'data', None) == b'captcha_reveal':
                                try:
                                    await client(GetBotCallbackAnswerRequest(peer=bot, msg_id=msg.id, data=b'captcha_reveal'))
                                except Exception:
                                    pass

            await asyncio.sleep(2.0)
            hist = await client(GetHistoryRequest(peer=bot, offset_id=0, offset_date=None, add_offset=0, limit=10, max_id=0, min_id=0, hash=0))
            dice_val = 0
            for msg in hist.messages:
                if msg.media and hasattr(msg.media, 'value') and getattr(msg.media, 'emoticon', None) == '🎰':
                    dice_val = msg.media.value
                    break

            # 4. Auth in WebApp
            res_wv = await client(RequestMainWebViewRequest(peer=bot, bot=bot, start_param='webapp', platform='android'))
            hash_part = res_wv.url.split('#')[1]
            m = re.search(r'tgWebAppData=([^&]+)', hash_part)
            if not m:
                res["error"] = "No tgWebAppData"
                return res
            init_data = urllib.parse.unquote(m.group(1))

            sess.get(f"{self.web_base}/?tgWebAppStartParam=webapp", timeout=10)
            auth_r = sess.post(f"{self.web_base}/api/auth/telegram", json={"initData": init_data, "did": "", "hw": "fp_mobile_android"}, timeout=10)
            if auth_r.status_code != 200:
                res["error"] = f"Auth status {auth_r.status_code}"
                return res

            uid = auth_r.json().get("uid")

            # Solve slot captcha if required
            cap_status = sess.get(f"{self.web_base}/api/captcha/status", timeout=10).json()
            if cap_status.get("required") and dice_val > 0:
                symbols = ["🍒", "🍋", "🍇", "7️⃣"]
                val = max(1, min(64, dice_val)) - 1
                r1, r2, r3 = val % 4, (val // 4) % 4, (val // 16) % 4
                combo = [symbols[r1], symbols[r2], symbols[r3]]
                c_sol = sess.post(f"{self.web_base}/api/captcha/solve", json={"combination": combo}, timeout=10).json()
                if not c_sol.get("correct"):
                    combo_rev = [symbols[r3], symbols[r2], symbols[r1]]
                    sess.post(f"{self.web_base}/api/captcha/solve", json={"combination": combo_rev}, timeout=10)
                await asyncio.sleep(3.0)
                # re-auth
                res_wv2 = await client(RequestMainWebViewRequest(peer=bot, bot=bot, start_param='webapp', platform='android'))
                init_data2 = urllib.parse.unquote(re.search(r'tgWebAppData=([^&]+)', res_wv2.url.split('#')[1]).group(1))
                sess.post(f"{self.web_base}/api/auth/telegram", json={"initData": init_data2, "did": "", "hw": "fp_mobile_android"}, timeout=10)

            # 5. Check & Spin Wheel
            sess.post(f"{self.web_base}/api/bonuses/wheel/check", json={"uid": uid}, timeout=10)
            w_spin = sess.post(f"{self.web_base}/api/bonuses/wheel/spin", json={"uid": uid}, timeout=10).json()

            if w_spin.get("ok"):
                res["prize"] = w_spin.get("prize", 0.0)
                res["balance"] = w_spin.get("balance", 0.0)
            elif w_spin.get("code") == "cooldown":
                res["error"] = "Cooldown"
                return res

            # Check withdraw info / wager requirement
            w_info = sess.get(f"{self.web_base}/api/withdraw/info?uid={uid}", timeout=10).json()
            bal = w_info.get("balance", res["balance"])
            res["balance"] = bal

            # 6. Automated Wagering (Hi-Lo strategy)
            rounds = 0
            while not w_info.get("eligible") and rounds < 50 and bal >= 0.1:
                rounds += 1
                try:
                    h_st = sess.post(f"{self.web_base}/api/hilo/start", json={"uid": uid, "bet": 0.1}, timeout=5).json()
                    if not h_st.get("ok"):
                        h_st = sess.get(f"{self.web_base}/api/hilo/state?uid={uid}", timeout=5).json()
                    if h_st.get("active"):
                        mults = h_st.get("choiceMultipliers", {})
                        choice = "higher" if (mults.get("higher") or 999) <= (mults.get("lower") or 999) else "lower"
                        g = sess.post(f"{self.web_base}/api/hilo/guess", json={"uid": uid, "choice": choice}, timeout=5).json()
                        if g.get("ok") and g.get("canCashout"):
                            co = sess.post(f"{self.web_base}/api/hilo/cashout", json={"uid": uid}, timeout=5).json()
                            bal = co.get("balance", bal)
                        else:
                            bal = g.get("balance", bal)
                except Exception:
                    pass
                await asyncio.sleep(0.5)
                w_info = sess.get(f"{self.web_base}/api/withdraw/info?uid={uid}", timeout=10).json()

            res["balance"] = bal

            # 7. Submit Withdrawal to xRocket
            if bal >= 0.1:
                t_res = int(time.time() * 1000)
                req_id = hex(t_res)[2:] + ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
                quote = sess.post(f"{self.web_base}/api/withdraw/quote", json={
                    "uid": uid, "amount": bal, "method": "xrocket", "coin": "USDT", "currency": "USD", "reqId": req_id
                }, timeout=10).json()

                if quote.get("pending") and quote.get("job"):
                    for _ in range(10):
                        await asyncio.sleep(1.0)
                        j = sess.get(f"{self.web_base}/api/withdraw/job?id={quote['job']}", timeout=10).json()
                        if not j.get("pending"):
                            quote = j
                            break

                token = quote.get("token")
                if token:
                    conf = sess.post(f"{self.web_base}/api/withdraw/confirm", json={"token": token, "reqId": req_id}, timeout=10).json()
                    if conf.get("pending") and conf.get("job"):
                        for _ in range(10):
                            await asyncio.sleep(1.0)
                            j2 = sess.get(f"{self.web_base}/api/withdraw/job?id={conf['job']}", timeout=10).json()
                            if not j2.get("pending"):
                                conf = j2
                                break
                    if conf.get("ok"):
                        res["withdrawn"] = True
                        res["request_id"] = conf.get("requestId")
                        res["success"] = True

        except Exception as e:
            res["error"] = str(e)
            logger.error(f"CG execution error: {e}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

        return res

async def activate_cheque_on_main(cheque_url: str) -> bool:
    """Activates captured xRocket / CryptoBot cheque directly on Xxxcalibur account"""
    if not os.path.exists(MAIN_SESSION):
        logger.warning(f"Main session {MAIN_SESSION} not found for cheque activation!")
        return False

    client = TelegramClient(MAIN_SESSION, 2040, "b18441a1ff607e10a989891a5462e627")
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return False

        if "xrocket" in cheque_url:
            m = re.search(r'startapp=(c_[a-zA-Z0-9_\-]+)', cheque_url) or re.search(r'start=(c_[a-zA-Z0-9_\-]+)', cheque_url)
            if m:
                code = m.group(1)
                bot = await client.get_input_entity("xrocket")
                await client.send_message(bot, f"/start {code}")
                await asyncio.sleep(2.0)
                logger.info(f"[💰 CHEQUE ACTIVATED] xRocket code {code} sent to Xxxcalibur!")
                return True
        elif "CryptoBot" in cheque_url:
            m = re.search(r'start=(CQ[a-zA-Z0-9_\-]+)', cheque_url)
            if m:
                code = m.group(1)
                bot = await client.get_input_entity("CryptoBot")
                await client.send_message(bot, f"/start {code}")
                await asyncio.sleep(2.0)
                logger.info(f"[💰 CHEQUE ACTIVATED] CryptoBot code {code} sent to Xxxcalibur!")
                return True
    except Exception as e:
        logger.error(f"Error activating cheque on Xxxcalibur: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    return False

async def check_pending_withdrawals_and_collect(state: dict):
    """Monitors pending withdrawal requests. When admin approves and cheque appears in chat, claims it to Xxxcalibur!"""
    pending = state.get("pending_withdrawals", [])
    if not pending:
        return

    remaining = []
    cheque_collected_flag = False

    for item in pending:
        s_file = item.get("session_file")
        if not s_file or not os.path.exists(s_file):
            continue

        req_id = item.get("request_id")
        client = TelegramClient(s_file, 2040, "b18441a1ff607e10a989891a5462e627")
        try:
            await client.connect()
            if not await client.is_user_authorized():
                remaining.append(item)
                continue

            bot = await client.get_input_entity("casinocgbot")
            hist = await client(GetHistoryRequest(peer=bot, offset_id=0, offset_date=None, add_offset=0, limit=10, max_id=0, min_id=0, hash=0))

            found_cheque = None
            for msg in hist.messages:
                if msg.reply_markup and hasattr(msg.reply_markup, 'rows'):
                    for row in msg.reply_markup.rows:
                        for b in row.buttons:
                            u = getattr(b, 'url', None) or ""
                            if ("xrocket" in u or "CryptoBot" in u) and ("start=" in u or "startapp=" in u):
                                found_cheque = u
                                break
                if msg.message:
                    urls = re.findall(r'https?://t\.me/(?:xrocket|CryptoBot)\S+', msg.message)
                    if urls:
                        found_cheque = urls[0]
                        break

            if found_cheque:
                log_event(state, f"🎉 Cheque captured for Request #{req_id}: {found_cheque}")
                ok_claim = await activate_cheque_on_main(found_cheque)
                if ok_claim:
                    log_event(state, f"✔ Cheque successfully deposited to main account (Xxxcalibur)!")
                    state["total_cheques_collected"] = state.get("total_cheques_collected", 0) + 1
                    cheque_collected_flag = True
                    # Queue account for sale on LZT
                    state.setdefault("accounts_to_sell", []).append({
                        "session_file": s_file,
                        "account": item.get("account")
                    })
                else:
                    remaining.append(item)
            else:
                remaining.append(item)
        except Exception as e:
            remaining.append(item)
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    state["pending_withdrawals"] = remaining
    save_json(STATE_FILE, state)

    # If cheque arrived, trigger next scaled cycle!
    if cheque_collected_flag:
        log_event(state, "🚀 Cheque confirmed! Triggering next autonomous cycle with dynamic scaling...")
        asyncio.create_task(run_autonomous_cycle(state))

async def process_accounts_for_sale(lzt: LZTClient, state: dict):
    """Cleans up used accounts and lists them on LZT Market for $0.60"""
    to_sell = state.get("accounts_to_sell", [])
    if not to_sell:
        return

    unprocessed = []
    for acc in to_sell:
        s_file = acc.get("session_file")
        if not s_file or not os.path.exists(s_file):
            continue

        try:
            # 1. Clean account name & leave channels
            client = TelegramClient(s_file, 2040, "b18441a1ff607e10a989891a5462e627")
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                clean_name = (me.first_name or "").replace("@casinocgbot", "").strip() or "User"
                try:
                    await client(UpdateProfileRequest(first_name=clean_name))
                    for ch in ["budka_ccbets", "chat_cgbet"]:
                        try:
                            ent = await client.get_input_entity(ch)
                            await client(LeaveChannelRequest(ent))
                        except Exception:
                            pass
                except Exception:
                    pass
            await client.disconnect()

            # 2. Extract auth_key and dc_id
            conn = sqlite3.connect(s_file)
            c = conn.cursor()
            c.execute("SELECT dc_id, auth_key FROM sessions")
            row = c.fetchone()
            conn.close()

            if row and row[1]:
                dc_id = row[0]
                auth_key_hex = row[1].hex()
                ok_sell, link_or_err = lzt.fast_sell(auth_key_hex, dc_id, price=0.60)
                if ok_sell:
                    log_event(state, f"✔ Account {acc.get('account')} published on LZT: {link_or_err}")
                    state.setdefault("sold_accounts", []).append({
                        "id": link_or_err,
                        "account": acc.get("account"),
                        "price": 0.60
                    })
                else:
                    unprocessed.append(acc)
            else:
                unprocessed.append(acc)
        except Exception as e:
            logger.warning(f"Error selling account {acc}: {e}")
            unprocessed.append(acc)

    state["accounts_to_sell"] = unprocessed
    save_json(STATE_FILE, state)

async def run_autonomous_cycle(state: dict):
    """Executes a cycle: determines batch scale -> buys on LZT -> spins CasinoCG -> submits withdrawal"""
    cfg = load_json(CONFIG_FILE, {})
    lzt_token = cfg.get("lzt_token") or "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9..."
    lzt = LZTClient(token=lzt_token)

    bals = lzt.get_balances()
    buying_bal_usd = 0.0
    for b in bals.get("balances", []):
        if b.get("balance_id") == 21026:
            buying_bal_usd = float(b.get("convertedBalance") or 0.0)
            break

    # Also consider main balance + hold
    main_bal = bals.get("balance", 0.0)
    hold_bal = bals.get("hold", 0.0)
    log_event(state, f"LZT Balances: Buying Account Bal: ${buying_bal_usd:.2f} | Main: {main_bal:.2f} ₽ | Hold: {hold_bal:.2f} ₽")

    # Adaptive scaling: 1 account if < $1.40, 2 if >= $1.40, 3 if >= $2.10
    batch_size = 1
    if buying_bal_usd >= 2.0:
        batch_size = 3
    elif buying_bal_usd >= 1.3:
        batch_size = 2

    state["current_scale"] = batch_size
    state["cycle_count"] = state.get("cycle_count", 1) + 1
    log_event(state, f"Starting Cycle #{state['cycle_count']} | Target Batch Size: {batch_size} accounts")

    # Search and buy
    items = lzt.search_premium_accounts(max_price=0.68, limit=batch_size * 2)
    bought_count = 0

    for it in items:
        if bought_count >= batch_size:
            break

        item_id = it.get("item_id")
        price = it.get("price", 0.64)
        title = it.get("title", "")

        log_event(state, f"Attempting purchase: #{item_id} (${price}) - {title[:45]}...")
        ok_buy, item_data = lzt.fast_buy(item_id, price=price, balance_id=21026)

        if ok_buy:
            bought_count += 1
            login_data = item_data.get("loginData", {})
            auth_key_hex = login_data.get("login") or item_data.get("login")
            dc_id = int(login_data.get("password") or 1)

            sess_name = f"prem_{item_id}.session"
            sess_path = os.path.join(SESSIONS_DIR, sess_name)
            create_session_from_auth_key(sess_path, auth_key_hex, dc_id)
            log_event(state, f"✔ Bought & created session: {sess_name}")

            # Run CG worker
            worker = CasinoCGWorker(sess_path)
            cg_res = await worker.execute_cg_cycle()

            if cg_res.get("withdrawn"):
                req_id = cg_res.get("request_id")
                amount = cg_res.get("balance", 0.0)
                state["total_withdrawn_usd"] = round(state.get("total_withdrawn_usd", 0.0) + amount, 2)
                log_event(state, f"🚀 WITHDRAWAL SUBMITTED! Request #{req_id} | Amount: ${amount} USDT")
                state.setdefault("pending_withdrawals", []).append({
                    "account": f"prem_{item_id}",
                    "session_file": sess_path,
                    "request_id": req_id,
                    "amount": amount,
                    "coin": "USDT",
                    "method": "xrocket",
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
            else:
                log_event(state, f"CG execution finished with note: {cg_res.get('error') or 'Completed'}")

            save_json(STATE_FILE, state)
            await asyncio.sleep(5.0)

    save_json(STATE_FILE, state)

async def start_casinocg_flywheel_daemon():
    """Background continuous daemon running 24/7 on Render"""
    logger.info("Initializing CasinoCG Autonomous Flywheel Daemon on Render...")
    state = load_flywheel_state()
    cfg = load_json(CONFIG_FILE, {})
    lzt_token = cfg.get("lzt_token") or "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9..."
    lzt = LZTClient(token=lzt_token)

    log_event(state, "CasinoCG 24/7 Flywheel Daemon is ACTIVE on Render!")

    while True:
        try:
            # 1. Check pending withdrawals & collect cheques
            await check_pending_withdrawals_and_collect(state)

            # 2. Process accounts for sale
            await process_accounts_for_sale(lzt, state)

            # 3. If no pending withdrawals and we have buying balance, auto-start cycle
            if not state.get("pending_withdrawals"):
                bals = lzt.get_balances()
                buying_bal = 0.0
                for b in bals.get("balances", []):
                    if b.get("balance_id") == 21026:
                        buying_bal = float(b.get("convertedBalance") or 0.0)
                        break
                if buying_bal >= 0.64:
                    log_event(state, f"No pending withdrawals and active buying balance (${buying_bal:.2f}). Starting cycle...")
                    await run_autonomous_cycle(state)

        except Exception as e:
            logger.error(f"Error in flywheel daemon loop: {e}")

        # Poll every 45 seconds
        await asyncio.sleep(45)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_casinocg_flywheel_daemon())
