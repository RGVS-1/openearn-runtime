import asyncio
import json
import logging
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone

from aiohttp import web
import requests
from telethon import TelegramClient, events
from telethon.tl.functions.messages import RequestAppWebViewRequest
from telethon.tl.types import InputBotAppShortName, MessageEntityTextUrl

import harvest_all_accounts
import pixelmania_runner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("sniper.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("all_in_one_farm")

def ensure_vault_decrypted():
    vault_key = os.environ.get("VAULT_KEY")
    if vault_key and os.path.exists("vault.enc") and not os.path.exists("accounts_db.json"):
        try:
            import io
            import zipfile
            from cryptography.fernet import Fernet
            logger.info("🔒 Decrypting vault.enc with VAULT_KEY...")
            with open("vault.enc", "rb") as vf:
                enc_bytes = vf.read()
            fernet = Fernet(vault_key.encode("utf-8"))
            dec_bytes = fernet.decrypt(enc_bytes)
            with zipfile.ZipFile(io.BytesIO(dec_bytes), "r") as zf:
                zf.extractall(".")
            logger.info("🔓 Vault extracted successfully!")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to decrypt vault: {e}")
            return False
    return os.path.exists("accounts_db.json")

ensure_vault_decrypted()

CONFIG_PATH = "config.json"
ACCOUNTS_DB_PATH = "accounts_db.json" if os.path.exists("accounts_db.json") else r"C:\Users\hoaki\Desktop\RB_Autimatic\accounts_db.json"
SESSIONS_DIR = "sessions"
DATABASE_PATH = "database.json"
PIXELMANIA_DB_PATH = "pixelmania_db.json"
PROMOS_HISTORY_PATH = "promos_history.json"

INTERCEPTED_PROMOS = []
ACTIVATION_HISTORY = []

def save_promos_history():
    try:
        with open(PROMOS_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "intercepted": INTERCEPTED_PROMOS[-40:],
                "activations": ACTIVATION_HISTORY[-40:]
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving promos history: {e}")

def load_promos_history():
    global INTERCEPTED_PROMOS, ACTIVATION_HISTORY
    if os.path.exists(PROMOS_HISTORY_PATH):
        try:
            with open(PROMOS_HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                INTERCEPTED_PROMOS = data.get("intercepted", [])
                ACTIVATION_HISTORY = data.get("activations", [])
        except Exception as e:
            logger.error(f"Error loading promos history: {e}")
    else:
        INTERCEPTED_PROMOS = [{
            "id": 313,
            "date": "2026-11-02T20:59:31.000Z",
            "targets": [{
                "platform": "cdgrader",
                "bot": "cdgraderBot",
                "voucher": "v_3X9xFf8ysum3",
                "url": "https://t.me/cdgraderBot/cdgrader?startapp=v_3X9xFf8ysum3"
            }],
            "text_preview": "CDGRADER Чек — v_3X9xFf8ysum3"
        }]
        ACTIVATION_HISTORY = [{
            "timestamp": "02.11.2026 23:59:31",
            "target": {
                "platform": "cdgrader",
                "bot": "cdgraderBot",
                "voucher": "v_3X9xFf8ysum3",
                "url": "https://t.me/cdgraderBot/cdgrader?startapp=v_3X9xFf8ysum3"
            },
            "success_count": 0,
            "total_accounts": 110,
            "reasons": {"Чек уже исчерпан другими (All claims taken)": 110},
            "elapsed_sec": 0.45
        }]
        save_promos_history()

load_promos_history()

LAST_HARVEST_DATE = None
LAST_PIXELMANIA_DATE = None
TOTAL_FARM_STATS = {
    "total_tot": 0,
    "total_stars": 0.0,
    "accounts_count": 0,
    "last_tapper_cycle": None,
    "last_daily_harvest": None,
    "last_pixelmania_run": None,
    "pixelmania_status": "IDLE"
}

def parse_channel_post(text: str, entities: list = None) -> list:
    targets = []
    all_urls = []
    if entities:
        for ent in entities:
            if isinstance(ent, MessageEntityTextUrl):
                all_urls.append(ent.url)
    
    plain_urls = re.findall(r'https?://[^\s\)]+', text)
    all_urls.extend(plain_urls)
    
    unique_urls = []
    for u in all_urls:
        if u not in unique_urls:
            unique_urls.append(u)
    
    for url in unique_urls:
        cd_m = re.search(r'cdgraderBot/cdgrader\?startapp=(v_[a-zA-Z0-9_\-]+)', url)
        if cd_m:
            targets.append({
                "platform": "cdgrader",
                "bot": "cdgraderBot",
                "app_short_name": "cdgrader",
                "voucher": cd_m.group(1),
                "url": url
            })
            
        gen_m = re.search(r't\.me/([a-zA-Z0-9_]+)/(?:[a-zA-Z0-9_]+)\?startapp=([a-zA-Z0-9_\-]+)', url)
        if gen_m and not cd_m:
            targets.append({
                "platform": "generic_startapp",
                "bot": gen_m.group(1),
                "start_param": gen_m.group(2),
                "url": url
            })

    code_match = re.search(r'(?:Промокод\s*[—\-:]*\s*[`"]?([A-Za-zА-Яа-я0-9_\-]+)[`"]?)', text, re.IGNORECASE)
    if code_match:
        code = code_match.group(1)
        if "skinsetup_bot" in text or "SKINSET" in text:
            targets.append({
                "platform": "skinset",
                "bot": "skinsetup_bot",
                "code": code
            })
        elif "TheCardHouse_bot" in text or "CARDHOUSE" in text:
            targets.append({
                "platform": "cardhouse",
                "bot": "TheCardHouse_bot",
                "code": code
            })
        else:
            targets.append({
                "platform": "generic_promo",
                "code": code,
                "raw_text": text[:150]
            })

    return targets

async def activate_cdgrader_single(acc_name: str, meta: dict, cfg: dict, voucher: str) -> dict:
    sess_path = os.path.join(SESSIONS_DIR, f"{acc_name}.session")
    if not os.path.exists(sess_path):
        return {"account": acc_name, "ok": False, "reason": "no_session"}

    dev = meta.get("device", {})
    proxy = meta.get("proxy", {}).get("telethon")
    user_agent = meta.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    init_data = None
    proxies_to_try = [proxy, None] if proxy else [None]
    last_err = None

    for cur_proxy in proxies_to_try:
        client = TelegramClient(
            sess_path,
            cfg["api_id"],
            cfg["api_hash"],
            proxy=cur_proxy,
            device_model=dev.get("device_model", "Desktop"),
            system_version=dev.get("system_version", "Windows 11 x64"),
            app_version=dev.get("app_version", "4.16.8 x64"),
            system_lang_code=dev.get("system_lang_code", "ru-RU"),
            lang_code=dev.get("lang_code", "ru"),
            connection_retries=1
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=8.0)
            if not await client.is_user_authorized():
                return {"account": acc_name, "ok": False, "reason": "unauthorized"}

            bot = await client.get_entity("cdgraderBot")
            res = await client(RequestAppWebViewRequest(
                peer=bot,
                app=InputBotAppShortName(bot_id=await client.get_input_entity(bot), short_name='cdgrader'),
                platform='android',
                start_param=voucher
            ))
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(res.url).fragment)
            init_data = parsed.get('tgWebAppData', [''])[0]
            break
        except Exception as e:
            last_err = e
            continue
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    if not init_data:
        return {"account": acc_name, "ok": False, "reason": f"mtproto_err: {last_err or 'no_init_data'}"}

    try:
        headers = {
            'authorization': f'tma {init_data}',
            'x-language': 'ru',
            'User-Agent': user_agent
        }
        # Auto-register / auth user in CatDog if not yet registered
        try:
            requests.post("https://api.catgrader.tg/auth/me", headers=headers, json={}, timeout=5)
        except Exception:
            pass

        r = requests.post("https://api.catgrader.tg/vouchers/redeem", headers=headers, json={}, timeout=8)
        if r.status_code == 200:
            return {"account": acc_name, "ok": True, "data": r.json()}
        elif r.status_code == 409:
            return {"account": acc_name, "ok": False, "status": 409, "reason": "Чек исчерпан другими"}
        else:
            reason_txt = r.text
            try:
                reason_txt = r.json().get("error", r.text)
            except Exception:
                pass
            return {"account": acc_name, "ok": False, "status": r.status_code, "reason": reason_txt}
    except Exception as e:
        return {"account": acc_name, "ok": False, "reason": f"http_err: {e}"}

async def dispatch_promo_targets(targets: list):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    with open(ACCOUNTS_DB_PATH, "r", encoding="utf-8") as f:
        rb_accs = json.load(f)

    valid_accounts = [
        acc for acc in rb_accs 
        if acc != "[KZ] Tamosyaaaaaa +77052241850 2026"
    ]

    for target in targets:
        logger.info(f"⚡ SNIPER: Dispatching {target['platform']} to {len(valid_accounts)} accounts...")
        sem = asyncio.Semaphore(25)
        
        async def sem_task(acc):
            async with sem:
                if target["platform"] == "cdgrader":
                    return await activate_cdgrader_single(acc, rb_accs[acc], cfg, target["voucher"])
                else:
                    return {"account": acc, "ok": False, "reason": f"unhandled platform {target['platform']}"}

        start_t = time.time()
        results = await asyncio.gather(*[sem_task(acc) for acc in valid_accounts], return_exceptions=True)
        elapsed = round(time.time() - start_t, 2)
        successes = sum(1 for r in results if isinstance(r, dict) and r.get("ok"))
        logger.info(f"Target {target['platform']} complete in {elapsed}s: {successes}/{len(valid_accounts)} ok.")
        
        reasons_summary = {}
        for r in results:
            if isinstance(r, dict) and not r.get("ok"):
                res_key = r.get("reason") or f"status_{r.get('status')}"
                reasons_summary[res_key] = reasons_summary.get(res_key, 0) + 1

        ACTIVATION_HISTORY.append({
            "timestamp": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S"),
            "target": target,
            "success_count": successes,
            "total_accounts": len(valid_accounts),
            "reasons": reasons_summary,
            "elapsed_sec": elapsed
        })
        save_promos_history()

PROCESSED_MESSAGE_IDS = set()

# --- Background Task 1: Telegram Realtime Listener ---
async def run_telegram_listener():
    while True:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            with open(ACCOUNTS_DB_PATH, "r", encoding="utf-8") as f:
                rb_accs = json.load(f)

            acc_name = "[RU] Xxxcalibur +79936124946 2025"
            meta = rb_accs.get(acc_name, {})
            sess_path = os.path.join(SESSIONS_DIR, f"{acc_name}.session")

            client = TelegramClient(
                sess_path,
                cfg["api_id"],
                cfg["api_hash"],
                proxy=None, # Direct cloud connection from Frankfurt has 1ms ping & zero proxy 407 errors
                **meta.get("device", {})
            )

            await client.connect()
            logger.info("Realtime listener connected to Telegram MTProto!")
            channel = await client.get_entity("lh_promocodes")
            
            # Ensure subscribed to channel for instant MTProto push delivery
            try:
                from telethon.tl.functions.channels import JoinChannelRequest
                await client(JoinChannelRequest(channel))
                logger.info("Subscribed to @lh_promocodes for realtime updates!")
            except Exception as e:
                logger.info(f"Subscription status: {e}")

            # Initialize last known message ID
            try:
                init_msgs = await client.get_messages(channel, limit=3)
                for m in init_msgs:
                    PROCESSED_MESSAGE_IDS.add(m.id)
                logger.info(f"Initialized with last message ID: {init_msgs[0].id if init_msgs else 'None'}")
            except Exception:
                pass

            def process_message(msg):
                if msg.id in PROCESSED_MESSAGE_IDS:
                    return
                PROCESSED_MESSAGE_IDS.add(msg.id)
                text = msg.text or ""
                logger.info(f"🚨 New promo in @lh_promocodes (ID: {msg.id}): {text[:100]}...")
                targets = parse_channel_post(text, msg.entities)
                if targets:
                    INTERCEPTED_PROMOS.append({
                        "id": msg.id,
                        "date": datetime.utcnow().isoformat(),
                        "targets": targets,
                        "text_preview": text[:120]
                    })
                    asyncio.create_task(dispatch_promo_targets(targets))

            @client.on(events.NewMessage(chats=channel))
            async def on_new_promo(event):
                process_message(event.message)

            # Backup poller every 3 seconds to guarantee zero missed posts
            async def backup_poller():
                while client.is_connected():
                    try:
                        recent = await client.get_messages(channel, limit=3)
                        for m in recent:
                            if m.id not in PROCESSED_MESSAGE_IDS:
                                logger.info(f"⚡ Backup poller detected new post #{m.id}!")
                                process_message(m)
                    except Exception:
                        pass
                    await asyncio.sleep(3)

            asyncio.create_task(backup_poller())
            await client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Listener error, reconnecting in 15s: {e}")
            await asyncio.sleep(15)

# --- Background Task 2: Continuous 5-min Tapper ---
async def run_tapper_loop():
    logger.info("Starting background 5-minute tapper loop...")
    await asyncio.sleep(20) # wait initial startup
    while True:
        try:
            import tapper_daemon
            await tapper_daemon.run_loop(max_rounds=1)
            TOTAL_FARM_STATS["last_tapper_cycle"] = datetime.utcnow().isoformat()
        except Exception as e:
            logger.error(f"Tapper loop error: {e}")
        
        logger.info("Tapper cycle complete. Sleeping 310s until next cycle...")
        await asyncio.sleep(310)

# --- Background Task 3: Scheduled Daily Harvest (Checkin + Free Cases) ---
async def run_daily_harvest_schedule():
    global LAST_HARVEST_DATE
    logger.info("Starting scheduled daily harvest watcher...")
    await asyncio.sleep(10)
    while True:
        try:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if LAST_HARVEST_DATE != today_str:
                logger.info(f"🌅 New day detected ({today_str})! Running full daily harvest on 110 accounts...")
                await harvest_all_accounts.main()
                LAST_HARVEST_DATE = today_str
                TOTAL_FARM_STATS["last_daily_harvest"] = datetime.utcnow().isoformat()
        except Exception as e:
            logger.error(f"Daily harvest watcher error: {e}")
        
        await asyncio.sleep(1800) # Check every 30 minutes

# --- Background Task 4: Scheduled Daily Pixelmania (Claim Daily + Tasks + Mine) ---
async def run_pixelmania_daily_schedule():
    global LAST_PIXELMANIA_DATE
    logger.info("Starting Pixelmania daily schedule watcher...")
    await asyncio.sleep(45) # Initial wait after startup
    while True:
        try:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if LAST_PIXELMANIA_DATE != today_str:
                logger.info(f"🎮 Starting daily Pixelmania run for {today_str} on all accounts...")
                TOTAL_FARM_STATS["pixelmania_status"] = "RUNNING"
                res = await pixelmania_runner.run_pixelmania_farm(mode="full")
                LAST_PIXELMANIA_DATE = today_str
                TOTAL_FARM_STATS["last_pixelmania_run"] = datetime.utcnow().isoformat()
                TOTAL_FARM_STATS["pixelmania_status"] = "IDLE"
                logger.info(f"Pixelmania daily run completed: {res}")
        except Exception as e:
            logger.error(f"Pixelmania schedule error: {e}")
            TOTAL_FARM_STATS["pixelmania_status"] = "ERROR"

        await asyncio.sleep(1800) # Check every 30 minutes

# --- Web Server Endpoints ---
async def handle_index(request):
    ensure_vault_decrypted()
    db_data = {}
    if os.path.exists(DATABASE_PATH):
        try:
            with open(DATABASE_PATH, "r", encoding="utf-8", errors="replace") as f:
                db_data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading {DATABASE_PATH}: {e}")

    tot = 0
    stars = 0.0
    for v in db_data.values():
        try:
            tot += int(v.get("tot_balance") or 0)
        except Exception:
            pass
        try:
            stars += float(v.get("balance_stars") or 0)
        except Exception:
            pass

    pm_db = {}
    if os.path.exists(PIXELMANIA_DB_PATH):
        try:
            with open(PIXELMANIA_DB_PATH, "r", encoding="utf-8", errors="replace") as f:
                pm_db = json.load(f)
        except Exception:
            pass

    total_pixels_mined = sum(v.get("pixels_mined_total", 0) for v in pm_db.values())
    golden_winners_count = 0
    if os.path.exists("WINNERS.json"):
        try:
            with open("WINNERS.json", "r", encoding="utf-8") as f:
                golden_winners_count = len(json.load(f))
        except Exception:
            pass

    stats_data = {
        "service": "TheOpenEarn + Pixelmania & Promo Sniper (All-In-One 24/7)",
        "status": "ONLINE",
        "timestamp_utc": datetime.utcnow().isoformat(),
        "openearn_stats": {
            "total_farm_tot": tot,
            "total_farm_stars": round(stars, 4),
            "accounts_total": len(db_data),
            "last_tapper_cycle": TOTAL_FARM_STATS["last_tapper_cycle"],
            "last_daily_harvest": TOTAL_FARM_STATS["last_daily_harvest"]
        },
        "pixelmania_stats": {
            "status": TOTAL_FARM_STATS.get("pixelmania_status", "IDLE"),
            "accounts_count": len(pm_db),
            "total_pixels_mined": total_pixels_mined,
            "golden_winners_count": golden_winners_count,
            "last_run": TOTAL_FARM_STATS.get("last_pixelmania_run")
        },
        "promo_sniper": {
            "channel": "@lh_promocodes",
            "intercepted_promos_count": len(INTERCEPTED_PROMOS),
            "recent_promos": INTERCEPTED_PROMOS[-15:],
            "recent_activations": ACTIVATION_HISTORY[-15:]
        }
    }

    accept = request.headers.get("Accept", "")
    if request.query.get("format") == "json" or ("application/json" in accept and "text/html" not in accept):
        return web.json_response(stats_data)

    from dashboard_template import render_dashboard_html
    html_content = render_dashboard_html(stats_data)
    return web.Response(text=html_content, content_type="text/html", charset="utf-8")

async def handle_debug(request):
    vault_status = ensure_vault_decrypted()
    return web.json_response({
        "cwd": os.getcwd(),
        "has_vault_key": bool(os.environ.get("VAULT_KEY")),
        "vault_enc_exists": os.path.exists("vault.enc"),
        "vault_decrypted": vault_status,
        "accounts_db_exists": os.path.exists("accounts_db.json"),
        "database_exists": os.path.exists("database.json"),
        "pixelmania_db_exists": os.path.exists(PIXELMANIA_DB_PATH),
        "sessions_count": len(os.listdir("sessions")) if os.path.exists("sessions") else 0,
        "files": [f for f in os.listdir(".") if not f.startswith(".") and not f.endswith(".session")]
    })

async def handle_health(request):
    # Endpoint for cron-job.org to keep Render alive
    return web.json_response({"status": "ok", "uptime": "alive", "utc": datetime.utcnow().isoformat()})

async def handle_manual_harvest(request):
    asyncio.create_task(harvest_all_accounts.main())
    return web.json_response({"status": "harvest_dispatched_in_background"})

async def handle_manual_pixelmania(request):
    TOTAL_FARM_STATS["pixelmania_status"] = "RUNNING"
    asyncio.create_task(pixelmania_runner.run_pixelmania_farm(mode="full"))
    return web.json_response({"status": "pixelmania_dispatched_in_background"})

async def handle_logs(request):
    log_lines = []
    for log_file in ["harvest.log", "sniper.log", "tapper_loop.log"]:
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    log_lines.extend(lines[-60:])
            except Exception:
                pass
    content = "".join(log_lines[-120:]) if log_lines else "Логи инициализируются на сервере..."
    return web.Response(text=content, content_type="text/plain", charset="utf-8")

def create_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/harvest", handle_manual_harvest)
    app.router.add_get("/pixelmania/run", handle_manual_pixelmania)
    app.router.add_get("/logs", handle_logs)
    app.router.add_get("/debug", handle_debug)
    return app

async def main():
    port = int(os.getenv("PORT", 8080))
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server online on port {port}. Ready for Render & cron-job.org.")

    t1 = asyncio.create_task(run_telegram_listener())
    t2 = asyncio.create_task(run_tapper_loop())
    t3 = asyncio.create_task(run_daily_harvest_schedule())
    t4 = asyncio.create_task(run_pixelmania_daily_schedule())

    try:
        await asyncio.gather(t1, t2, t3, t4)
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process stopped.")
