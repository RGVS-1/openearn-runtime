import asyncio
import hashlib
import logging
import random
import httpx
from typing import Dict, Any, Optional

logger = logging.getLogger("pacocash.verifier")

TASKMASK_BASE = "https://app.taskmask.site"

async def verify_taskmask(
    init_data: str,
    launch: str,
    proxy_url: Optional[str] = None,
    user_agent: Optional[str] = None,
    client_meta: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Simulates the TaskMask anti-fraud verification workflow:
    1. /pay-message/af/session
    2. /pay-message/af/check
    3. /pay-message/af/result (polling)
    """
    ua = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    meta = client_meta or {}

    headers = {
        "Content-Type": "application/json",
        "User-Agent": ua,
        "Origin": TASKMASK_BASE,
        "Referer": f"{TASKMASK_BASE}/pay-message/verify",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    transport_args = {"timeout": 25.0}
    if proxy_url:
        transport_args["proxy"] = proxy_url

    async with httpx.AsyncClient(**transport_args) as client:
        # Step 1: /pay-message/af/session
        payload_session = {
            "init_data": init_data,
            "launch": launch
        }
        res_session = await client.post(
            f"{TASKMASK_BASE}/pay-message/af/session",
            json=payload_session,
            headers=headers
        )
        if res_session.status_code != 200:
            return {
                "ok": False,
                "error": f"Session request failed: {res_session.status_code} {res_session.text}"
            }

        session_data = res_session.json()
        af_session = session_data.get("session")
        marker = session_data.get("marker")
        if not af_session:
            return {"ok": False, "error": f"No session returned: {session_data}"}

        # Step 2: /pay-message/af/check
        # Generate canvas and webgl hashes matching client meta
        canvas_salt = f"canvas_{af_session}_{random.randint(1000, 9999)}"
        webgl_salt = f"webgl_{af_session}_{random.randint(1000, 9999)}"
        canvas_hash = hashlib.sha256(canvas_salt.encode()).hexdigest()
        webgl_hash = hashlib.sha256(webgl_salt.encode()).hexdigest()

        features = {
            "platform": "tdesktop",
            "version": "9.6",
            "os": "Windows",
            "browser": "Chromium",
            "language": meta.get("language", "ru-RU"),
            "timezone": meta.get("timezone", "Europe/Moscow"),
            "screen": f"{meta.get('screenWidth', 1920)}x{meta.get('screenHeight', 1080)}@1",
            "storage": "Telegram storage API available",
            "biometric": "",
            "fp_version": "1",
            "canvas": canvas_hash,
            "webgl": webgl_hash
        }

        payload_check = {
            "session": af_session,
            "marker": marker,
            "features": features
        }

        res_check = await client.post(
            f"{TASKMASK_BASE}/pay-message/af/check",
            json=payload_check,
            headers=headers
        )
        if res_check.status_code != 200:
            return {
                "ok": False,
                "error": f"Check request failed: {res_check.status_code} {res_check.text}"
            }

        # Step 3: Poll /pay-message/af/result
        max_polls = 15
        for poll_idx in range(max_polls):
            await asyncio.sleep(2)
            res_result = await client.post(
                f"{TASKMASK_BASE}/pay-message/af/result",
                json={"session": af_session},
                headers=headers
            )
            if res_result.status_code == 200:
                data = res_result.json()
                if not data.get("pending"):
                    return {
                        "ok": data.get("ok", False),
                        "message": data.get("message", ""),
                        "items": data.get("items", [])
                    }

        return {
            "ok": False,
            "error": "Verification timeout (still pending after 30 seconds)"
        }
