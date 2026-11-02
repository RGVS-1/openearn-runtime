import asyncio
import json
import logging
import os
import re
import urllib.parse
from typing import Dict, Any, Optional, List

import requests
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import StartBotRequest, RequestAppWebViewRequest, ImportChatInviteRequest
from telethon.tl.types import InputUser, InputBotAppShortName
from telethon.errors.common import AuthKeyNotFound

from .captcha_solver import solve_emoji_captcha_if_present
from .proxy_helper import get_working_proxy_for_account, mark_proxy_dead

logger = logging.getLogger("openearn.worker")

APP_API_BASE = "https://app.theopenearn.info/api"

async def process_account(
    account_name: str,
    session_file: str,
    api_id: int,
    api_hash: str,
    referral_code: str,
    meta: dict,
    claim_checkin: bool = True,
    do_channel_tasks: bool = True
) -> Dict[str, Any]:
    """
    Executes full TheOpenEarn onboarding and task execution for a single account:
    1. Connect via dedicated proxy with spoofed device fingerprint (Windows 11 / Desktop)
    2. Start @TheOpenEarnBot with assigned referral parameter
    3. Complete language selection (RU), age verification (18+), terms acceptance
    4. Click 'Задания' & solve emoji security captcha automatically
    5. Request WebApp URL for @TheOpenEarnAppBot & extract initData
    6. Claim daily checkin (+15 TOT, daily streak)
    7. Execute available channel subscription tasks via Telethon & verify via API
    8. Retrieve final user stats and referral code
    9. Disconnect cleanly
    """
    dev = meta.get("device", {
        "device_model": "Desktop",
        "system_version": "Windows 11 x64",
        "app_version": "4.16.8 x64",
        "system_lang_code": "ru-RU",
        "lang_code": "ru"
    })

    working_proxy = get_working_proxy_for_account(account_name, meta)
    tel_proxy = working_proxy.get("telethon") if isinstance(working_proxy, dict) else None
    http_proxy = working_proxy.get("http_url") if isinstance(working_proxy, dict) else None
    user_agent = meta.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

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

    result: Dict[str, Any] = {
        "ok": False,
        "account": account_name,
        "referral_used": referral_code,
        "own_referral_code": None,
        "user_id": None,
        "username": None,
        "balance_stars": "0",
        "tot_balance": 0,
        "checkin_claimed": False,
        "tasks_done": 0,
        "error": None
    }

    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=18.0)
        except AuthKeyNotFound:
            result["error"] = "AUTH_KEY_NOT_FOUND (сессия деактивирована в Telegram)"
            return result
        except asyncio.TimeoutError:
            # Mark proxy dead and retry once with a rotated proxy
            if tel_proxy:
                mark_proxy_dead(tel_proxy.get("addr", ""))
                new_p = get_working_proxy_for_account(account_name, meta, force_rotate=True)
                if new_p:
                    tel_proxy = new_p.get("telethon")
                    client = TelegramClient(
                        session_file, api_id, api_hash, proxy=tel_proxy,
                        device_model=dev.get("device_model", "Desktop"),
                        system_version=dev.get("system_version", "Windows 11 x64"),
                        app_version=dev.get("app_version", "4.16.8 x64"),
                        system_lang_code=dev.get("system_lang_code", "ru-RU"),
                        lang_code=dev.get("lang_code", "ru")
                    )
                    await asyncio.wait_for(client.connect(), timeout=18.0)
                else:
                    result["error"] = "PROXY_TIMEOUT (все запасные прокси недоступны)"
                    return result
            else:
                result["error"] = "PROXY_TIMEOUT"
                return result
        except Exception as e:
            result["error"] = f"CONNECTION_ERROR ({e})"
            return result

        if not await client.is_user_authorized():
            result["error"] = "UNAUTHORIZED (сессия не авторизована)"
            return result

        me = await client.get_me()
        result["user_id"] = me.id
        result["username"] = me.username or ""
        logger.info(f"[{account_name}] Connected as {me.first_name} (@{me.username}) ID={me.id}")

        # 1. Start @TheOpenEarnBot with referral
        bot_entity = await client.get_entity("TheOpenEarnBot")
        bot_input = InputUser(bot_entity.id, bot_entity.access_hash)

        history = await client.get_messages(bot_entity, limit=5)
        already_started = any(m.id for m in history if m.text and ("/start" in m.text or "Добро пожаловать" in m.text))

        if not already_started:
            logger.info(f"[{account_name}] Sending /start {referral_code} to @TheOpenEarnBot...")
            await client(StartBotRequest(
                bot=bot_input,
                peer=bot_input,
                start_param=referral_code
            ))
            await asyncio.sleep(2.0)
        else:
            logger.info(f"[{account_name}] Bot was already started previously.")

        # 2. Complete onboarding dialog steps (Language -> Age -> Terms)
        for _ in range(3):
            msgs = await client.get_messages(bot_entity, limit=3)
            dialog_progressed = False

            for m in msgs:
                if not m.buttons:
                    continue
                for row in m.buttons:
                    for b in row:
                        if b.data == b'set_lang_first_ru':
                            logger.info(f"[{account_name}] Setting language to Russian...")
                            await b.click()
                            dialog_progressed = True
                            await asyncio.sleep(1.5)
                            break
                        elif b.data == b'age_confirm_yes':
                            logger.info(f"[{account_name}] Confirming age 18+...")
                            await b.click()
                            dialog_progressed = True
                            await asyncio.sleep(1.5)
                            break
                        elif b.data == b'terms_accept':
                            logger.info(f"[{account_name}] Accepting terms...")
                            await b.click()
                            dialog_progressed = True
                            await asyncio.sleep(1.5)
                            break
                    if dialog_progressed:
                        break
                if dialog_progressed:
                    break

            if not dialog_progressed:
                break

        # 3. Open Tasks menu in bot & solve captcha
        msgs = await client.get_messages(bot_entity, limit=3)
        for m in msgs:
            if m.buttons:
                for row in m.buttons:
                    for b in row:
                        if b.data == b'tasks':
                            logger.info(f"[{account_name}] Clicking 'Задания'...")
                            try:
                                await b.click()
                                await asyncio.sleep(2.0)
                            except Exception:
                                pass
                            break

        # Check and solve emoji captcha
        solved = await solve_emoji_captcha_if_present(client, bot_entity)
        if solved:
            logger.info(f"[{account_name}] Emoji captcha solved successfully!")
            await asyncio.sleep(1.5)

        # 4. Open Mini App via @TheOpenEarnAppBot
        logger.info(f"[{account_name}] Requesting Mini App WebApp...")
        app_bot = await client.get_entity("TheOpenEarnAppBot")
        app_input = InputUser(app_bot.id, app_bot.access_hash)

        web_view = await client(RequestAppWebViewRequest(
            peer=app_bot,
            app=InputBotAppShortName(bot_id=app_input, short_name='run'),
            platform='android',
            start_param=referral_code
        ))

        raw_url = web_view.url
        parsed = urllib.parse.urlparse(raw_url)
        params = urllib.parse.parse_qs(parsed.fragment)
        init_data = params.get('tgWebAppData', [''])[0]

        if not init_data:
            result["error"] = "FAILED_TO_GET_INITDATA"
            return result

        api_headers = {
            "Content-Type": "application/json",
            "Authorization": f"tma {init_data}",
            "User-Agent": user_agent,
            "Origin": "https://app.theopenearn.info",
            "Referer": "https://app.theopenearn.info/"
        }

        # 5. Claim Daily Checkin
        if claim_checkin:
            try:
                r_check = requests.post(
                    f"{APP_API_BASE}/checkin/claim",
                    headers=api_headers,
                    json={"platform": "android"},
                    timeout=10
                )
                if r_check.status_code == 200:
                    data = r_check.json()
                    result["checkin_claimed"] = True
                    logger.info(f"[{account_name}] Claimed daily checkin! Day: {data.get('day')}, Reward: {data.get('tot_amount')} TOT")
                elif r_check.status_code in [400, 409]:
                    logger.info(f"[{account_name}] Daily checkin already claimed today.")
                    result["checkin_claimed"] = True
            except Exception as e:
                logger.warning(f"[{account_name}] Checkin claim request error: {e}")

        # 5b. Play Tapper for +100 TOT
        try:
            r_tap_st = requests.get(f"{APP_API_BASE}/earn", headers=api_headers, timeout=10)
            if r_tap_st.status_code == 200:
                t_data = r_tap_st.json()
                req_taps = t_data.get("taps_required", 100)
                cur_prog = t_data.get("cycle_progress", 0)
                needed = max(0, req_taps - cur_prog)
                if needed > 0 and not t_data.get("cooldown_until"):
                    r_tap = requests.post(f"{APP_API_BASE}/earn", headers=api_headers, json={"taps": needed}, timeout=10)
                    if r_tap.status_code == 200:
                        logger.info(f"[{account_name}] Tapper completed! +100 TOT collected.")
                        result["tapper_completed"] = True
        except Exception as e:
            logger.debug(f"[{account_name}] Tapper error: {e}")

        # 5c. Open Daily Free Case (Win Stars & Gifts)
        try:
            r_case = requests.post(f"{APP_API_BASE}/case/open", headers=api_headers, timeout=10)
            if r_case.status_code == 200:
                c_data = r_case.json()
                logger.info(f"[{account_name}] Opened Free Case: won {c_data.get('label')} {c_data.get('prize_type')}!")
                result["case_prize"] = c_data
            else:
                logger.debug(f"[{account_name}] Free Case status: {r_case.status_code} {r_case.text}")
        except Exception as e:
            logger.debug(f"[{account_name}] Free Case error: {e}")

        # 5d. Case tasks (Social shares for extra rewards)
        try:
            requests.post(f"{APP_API_BASE}/case/friends/shared", headers=api_headers, timeout=6)
            requests.post(f"{APP_API_BASE}/case/story/shared", headers=api_headers, timeout=6)
        except Exception:
            pass

        # 6. Channel subscription tasks execution
        if do_channel_tasks:
            try:
                r_tasks = requests.get(f"{APP_API_BASE}/tasks/ads?locale=ru", headers=api_headers, timeout=10)
                if r_tasks.status_code == 200:
                    tasks_list = r_tasks.json()
                    if isinstance(tasks_list, list):
                        for task in tasks_list:
                            task_id = task.get("id")
                            t_type = task.get("task_type")
                            target_url = task.get("target_url", "")
                            
                            if t_type == "channel" and target_url and ("t.me/" in target_url or "@" in target_url):
                                try:
                                    channel_target = target_url.replace("https://t.me/+", "+").replace("https://t.me/", "")
                                    logger.info(f"[{account_name}] Joining task channel: {channel_target} (Task #{task_id})")
                                    if channel_target.startswith("+"):
                                        try:
                                            await client(ImportChatInviteRequest(hash=channel_target[1:]))
                                        except Exception:
                                            pass
                                    else:
                                        await client(JoinChannelRequest(channel_target))
                                    await asyncio.sleep(1.5)

                                    # Notify open
                                    requests.post(f"{APP_API_BASE}/tasks/ads/{task_id}/open", headers=api_headers, timeout=8)
                                    # Verify check
                                    r_chk = requests.post(f"{APP_API_BASE}/tasks/ads/{task_id}/check", headers=api_headers, timeout=8)
                                    if r_chk.status_code == 200 and r_chk.json().get("ok"):
                                        result["tasks_done"] += 1
                                        logger.info(f"[{account_name}] Task #{task_id} completed successfully!")
                                except Exception as err_t:
                                    logger.debug(f"[{account_name}] Task #{task_id} skipped: {err_t}")
                            elif target_url:
                                try:
                                    requests.post(f"{APP_API_BASE}/tasks/ads/{task_id}/open", headers=api_headers, timeout=8)
                                except Exception:
                                    pass
            except Exception as e:
                logger.debug(f"[{account_name}] Error fetching task ads: {e}")

        # 7. Get updated User profile stats
        try:
            r_user = requests.get(f"{APP_API_BASE}/user", headers=api_headers, timeout=10)
            if r_user.status_code == 200:
                u_data = r_user.json()
                result["balance_stars"] = str(u_data.get("balance", "0"))
                result["tot_balance"] = u_data.get("tot_balance", 0)
                result["own_referral_code"] = u_data.get("referral_code")
                result["tasks_completed_total"] = u_data.get("tasks_completed", 0)
        except Exception as e:
            logger.debug(f"[{account_name}] Error reading final user profile: {e}")

        result["ok"] = True
        return result

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
