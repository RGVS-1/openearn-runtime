import asyncio
import os
import json
import uuid
import random
import urllib.parse
import logging
from typing import Dict, Any, Optional

import httpx
from telethon import TelegramClient
from telethon.tl.functions.messages import RequestAppWebViewRequest, StartBotRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputUser, InputBotAppShortName
from telethon.errors.common import AuthKeyNotFound

from .map_manager import map_mgr

logger = logging.getLogger("pixelmania.worker")

API_BASE = "https://pixxxxelmania.io/api/v1"
WINNERS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "WINNERS.json")

def record_winner(acc_name: str, phone: str, win_data: dict):
    entry = {
        "account": acc_name,
        "phone": phone,
        "win_data": win_data,
        "timestamp": str(asyncio.get_event_loop().time())
    }
    winners = []
    if os.path.exists(WINNERS_FILE):
        try:
            with open(WINNERS_FILE, "r", encoding="utf-8") as f:
                winners = json.load(f)
        except Exception:
            pass
    winners.append(entry)
    with open(WINNERS_FILE, "w", encoding="utf-8") as f:
        json.dump(winners, f, ensure_ascii=False, indent=2)

async def run_single_account(
    acc_name: str,
    session_file: str,
    meta: dict,
    config: dict
) -> Dict[str, Any]:
    dev = meta.get("device", {
        "device_model": "Dell XPS 15 9530",
        "system_version": "Windows 11 Pro",
        "app_version": "5.4.1 x64",
        "system_lang_code": "ru-RU",
        "lang_code": "ru"
    })
    proxy_info = meta.get("proxy", {})
    tel_proxy = proxy_info.get("telethon") if proxy_info else None
    
    # HTTP proxy for httpx
    http_proxy = None
    if tel_proxy:
        u = tel_proxy.get("username", "")
        p = tel_proxy.get("password", "")
        addr = tel_proxy.get("addr", "")
        port = tel_proxy.get("port", "")
        if u and p:
            http_proxy = f"http://{u}:{p}@{addr}:{port}"
        else:
            http_proxy = f"http://{addr}:{port}"

    user_agent = meta.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    api_id = config.get("api_id", 32293468)
    api_hash = config.get("api_hash", "0897266f179723de0640905e2f7860f3")
    referral_param = config.get("referral_param", "ref_4690afd1-fc25-4d6e-9a9a-5c3aa2f25563")
    bot_username = config.get("bot_username", "pixel_mania_bot")
    app_name = config.get("app_name", "app")
    claim_channel_tasks = config.get("claim_channel_tasks", True)
    mine_all = config.get("mine_all_pixels", True)

    result = {
        "account": acc_name,
        "phone": "Unknown",
        "status": "OK",
        "daily_claimed": False,
        "tasks_claimed": 0,
        "pixels_mined": 0,
        "golden_found": False,
        "initial_stars": 0,
        "remaining_stars": 0,
        "error": None
    }

    # 1. Connect Telegram Client
    client = TelegramClient(
        session_file,
        api_id,
        api_hash,
        proxy=tel_proxy,
        device_model=dev.get("device_model", "Desktop"),
        system_version=dev.get("system_version", "Windows 11 x64"),
        app_version=dev.get("app_version", "5.4.1 x64"),
        system_lang_code=dev.get("system_lang_code", "ru-RU"),
        lang_code=dev.get("lang_code", "ru"),
        connection_retries=2,
        retry_delay=1
    )

    init_data = None
    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=14.0)
        except AuthKeyNotFound:
            result["status"] = "DEAD_AUTH_KEY"
            result["error"] = "AuthKeyNotFound (сессия отключена Telegram)"
            return result
        except asyncio.TimeoutError:
            result["status"] = "PROXY_TIMEOUT"
            result["error"] = "Таймаут подключения прокси"
            return result
        except Exception as e:
            result["status"] = "CONNECTION_ERROR"
            result["error"] = str(e)
            return result

        if not await client.is_user_authorized():
            result["status"] = "UNAUTHORIZED"
            result["error"] = "Сессия не авторизована"
            await client.disconnect()
            return result

        me = await client.get_me()
        result["phone"] = me.phone or "Unknown"

        bot_entity = await client.get_input_entity(bot_username)
        bot = InputUser(bot_entity.user_id, bot_entity.access_hash)

        # Send start command if needed
        try:
            await client(StartBotRequest(bot=bot, peer=bot, start_param=referral_param))
        except Exception:
            pass

        # Join sponsor channels if enabled
        if claim_channel_tasks:
            channels = config.get("channels_to_join", ["pixelmania", "t0nenjoyer", "dailyenjoyer"])
            for ch in channels:
                try:
                    await client(JoinChannelRequest(ch))
                    await asyncio.sleep(random.uniform(0.5, 1.2))
                except Exception:
                    pass

        # Get WebApp initData
        platform_name = "android" if "android" in str(dev.get("system_version", "")).lower() else "tdesktop"
        web_view = await client(RequestAppWebViewRequest(
            peer=bot,
            app=InputBotAppShortName(bot_id=bot, short_name=app_name),
            platform=platform_name,
            start_param=referral_param,
            write_allowed=True
        ))
        
        parsed = urllib.parse.urlparse(web_view.url)
        params = urllib.parse.parse_qs(parsed.fragment)
        init_data = params.get("tgWebAppData", [None])[0]

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    if not init_data:
        result["status"] = "NO_INIT_DATA"
        result["error"] = "Не удалось получить tgWebAppData от Telegram"
        return result

    # 2. HTTP Interaction with pixxxxelmania.io API
    http_headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://pixxxxelmania.io",
        "Referer": "https://pixxxxelmania.io/",
        "X-Client-Capabilities": "star-rewards,daily-pixel,leaderboard-rewards,leaderboard-privacy,daily-rewards,task-codes,task-images"
    }

    try:
        with httpx.Client(proxy=http_proxy, headers=http_headers, timeout=20.0) as http:
            # 2.1 Auth (with retry on 502/503/deadline_exceeded)
            r_auth = None
            for attempt in range(3):
                r_auth = http.post(f"{API_BASE}/auth/telegram", json={"initData": init_data})
                if r_auth.status_code == 200:
                    break
                if r_auth.status_code in (500, 502, 503, 504, 429):
                    await asyncio.sleep(2.0 + attempt * 1.5)
                    continue
                break

            if not r_auth or r_auth.status_code != 200:
                result["status"] = "AUTH_API_ERROR"
                result["error"] = f"Auth failed with HTTP {getattr(r_auth, 'status_code', 0)}: {getattr(r_auth, 'text', '')}"
                return result

            auth_res = r_auth.json()
            csrf = auth_res.get("data", {}).get("csrfToken")
            epoch = auth_res.get("stateEpoch")
            http.headers["X-CSRF-Token"] = csrf
            http.headers["X-State-Epoch"] = epoch

            wallet = auth_res.get("data", {}).get("me", {}).get("wallet", {})
            stars = int(wallet.get("mainStars", 0)) + int(wallet.get("freePixels", 0)) + int(wallet.get("totalStars", 0))
            result["initial_stars"] = stars

            # 2.2 Claim Daily Pixel
            if config.get("claim_daily", True):
                try:
                    cmd_key = str(uuid.uuid4())
                    http.headers["Idempotency-Key"] = cmd_key
                    r_daily = http.post(f"{API_BASE}/me/daily-pixel", json={})
                    http.headers.pop("Idempotency-Key", None)
                    if r_daily.status_code == 200:
                        daily_data = r_daily.json()
                        epoch = daily_data.get("stateEpoch", epoch)
                        http.headers["X-State-Epoch"] = epoch
                        if daily_data.get("data", {}).get("claimed"):
                            result["daily_claimed"] = True
                            wallet = daily_data.get("data", {}).get("wallet", wallet)
                except Exception as e:
                    logger.warning(f"[{acc_name}] Daily claim error: {e}")

            # 2.3 Channel Tasks
            if claim_channel_tasks:
                try:
                    r_tasks = http.get(f"{API_BASE}/tasks?limit=50")
                    if r_tasks.status_code == 200:
                        t_data = r_tasks.json()
                        epoch = t_data.get("stateEpoch", epoch)
                        http.headers["X-State-Epoch"] = epoch
                        items = t_data.get("data", {}).get("items", [])
                        for t in items:
                            if t.get("status") == "available":
                                http.headers["Idempotency-Key"] = str(uuid.uuid4())
                                r_ver = http.post(f"{API_BASE}/tasks/{t['id']}/verify", json={})
                                http.headers.pop("Idempotency-Key", None)
                                if r_ver.status_code == 200:
                                    v_res = r_ver.json()
                                    epoch = v_res.get("stateEpoch", epoch)
                                    http.headers["X-State-Epoch"] = epoch
                                    if v_res.get("data", {}).get("status") == "verified":
                                        http.headers["Idempotency-Key"] = str(uuid.uuid4())
                                        r_claim = http.post(f"{API_BASE}/tasks/{t['id']}/claim", json={})
                                        http.headers.pop("Idempotency-Key", None)
                                        if r_claim.status_code == 200:
                                            result["tasks_claimed"] += 1
                                            c_res = r_claim.json()
                                            epoch = c_res.get("stateEpoch", epoch)
                                            http.headers["X-State-Epoch"] = epoch
                                            wallet = c_res.get("data", {}).get("wallet", wallet)
                except Exception as e:
                    logger.warning(f"[{acc_name}] Tasks claim error: {e}")

            # 2.4 Mine / Open Pixels
            if mine_all:
                # Refresh me & wallet
                try:
                    r_me = http.get(f"{API_BASE}/me")
                    if r_me.status_code == 200:
                        me_json = r_me.json()
                        epoch = me_json.get("stateEpoch", epoch)
                        http.headers["X-State-Epoch"] = epoch
                        wallet = me_json.get("data", {}).get("wallet", wallet)
                except Exception:
                    pass

                # Get season & map
                r_season = http.get(f"{API_BASE}/seasons/current")
                if r_season.status_code == 200:
                    s_json = r_season.json()
                    season_id = s_json.get("data", {}).get("id")
                    epoch = s_json.get("stateEpoch", epoch)
                    http.headers["X-State-Epoch"] = epoch

                    r_map = http.get(f"{API_BASE}/seasons/{season_id}/map")
                    if r_map.status_code == 200:
                        m_json = r_map.json()
                        epoch = m_json.get("stateEpoch", epoch)
                        http.headers["X-State-Epoch"] = epoch
                        chunks = m_json.get("data", {}).get("chunks", [])
                        map_mgr.update_map(season_id, chunks)

                    # Total attempts
                    free_px = int(wallet.get("freePixels", 0))
                    main_st = int(wallet.get("mainStars", 0))
                    tot_st = int(wallet.get("totalStars", 0))
                    current_balance = max(free_px + main_st, tot_st)

                    while current_balance > 0:
                        cand = map_mgr.pick_candidate_pixel()
                        if not cand:
                            break
                        x, y = cand

                        # Quote
                        quote_body = {
                            "seasonId": season_id,
                            "anchor": {"x": x, "y": y},
                            "tool": 1
                        }
                        r_quote = http.post(f"{API_BASE}/mine/quote", json=quote_body)
                        if r_quote.status_code != 200:
                            break

                        q_json = r_quote.json()
                        epoch = q_json.get("stateEpoch", epoch)
                        http.headers["X-State-Epoch"] = epoch
                        q_data = q_json.get("data", {})

                        if q_data.get("maxCount", 0) == 0:
                            map_mgr.mark_coordinate(x, y)
                            continue

                        if q_data.get("deficitStars", "0") != "0":
                            # Not enough stars
                            break

                        # Mine!
                        mine_body = {
                            "seasonId": season_id,
                            "anchor": {"x": x, "y": y},
                            "tool": 1,
                            "maxPriceStars": q_data.get("maxPriceStars", "1")
                        }
                        http.headers["Idempotency-Key"] = str(uuid.uuid4())
                        r_mine = http.post(f"{API_BASE}/mine", json=mine_body)
                        http.headers.pop("Idempotency-Key", None)

                        if r_mine.status_code != 200:
                            break

                        mine_json = r_mine.json()
                        epoch = mine_json.get("stateEpoch", epoch)
                        http.headers["X-State-Epoch"] = epoch
                        m_res = mine_json.get("data", {})

                        result["pixels_mined"] += 1
                        map_mgr.mark_coordinate(x, y)

                        # Check for victory / golden pixel / gifts!
                        if m_res.get("won") is True or m_res.get("gifts"):
                            result["golden_found"] = True
                            record_winner(acc_name, result["phone"], m_res)
                            logger.info(f"🏆 [GOLDEN PIXEL / WINNER FOUND!] Account: {acc_name}, Data: {m_res}")

                        wallet = m_res.get("wallet", wallet)
                        free_px = int(wallet.get("freePixels", 0))
                        main_st = int(wallet.get("mainStars", 0))
                        tot_st = int(wallet.get("totalStars", 0))
                        current_balance = max(free_px + main_st, tot_st)

                        await asyncio.sleep(random.uniform(0.6, 1.3))

            # Final stars balance
            result["remaining_stars"] = int(wallet.get("mainStars", 0)) + int(wallet.get("freePixels", 0))

    except Exception as e:
        result["status"] = "HTTP_ERROR"
        result["error"] = str(e)

    map_mgr.save_tried()
    return result
