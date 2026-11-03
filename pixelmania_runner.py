import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Dict, Any, List

from core.pixel_worker import run_single_account, WINNERS_FILE
from core.map_manager import map_mgr

logger = logging.getLogger("pixelmania_runner")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "pixelmania_config.json")
DATABASE_PATH = os.path.join(BASE_DIR, "pixelmania_db.json")
ACCOUNTS_DB_PATH = os.path.join(BASE_DIR, "accounts_db.json")
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")

def load_config() -> dict:
    default_config = {
        "api_id": 32293468,
        "api_hash": "0897266f179723de0640905e2f7860f3",
        "referral_param": "ref_4690afd1-fc25-4d6e-9a9a-5c3aa2f25563",
        "bot_username": "pixel_mania_bot",
        "app_name": "app",
        "claim_daily": True,
        "claim_channel_tasks": True,
        "mine_all_pixels": True,
        "delay_min": 2,
        "delay_max": 5,
        "batch_size": 3,
        "channels_to_join": ["pixelmania", "t0nenjoyer", "dailyenjoyer"]
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                default_config.update(cfg)
        except Exception as e:
            logger.error(f"Error loading pixelmania_config.json: {e}")
    return default_config

def load_database() -> dict:
    if os.path.exists(DATABASE_PATH):
        try:
            with open(DATABASE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading pixelmania_db.json: {e}")
    return {}

def save_database(db: dict):
    try:
        with open(DATABASE_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving pixelmania_db.json: {e}")

async def run_pixelmania_farm(mode: str = "full") -> dict:
    """
    Runs Pixelmania claim and mining across all available accounts in batches.
    """
    logger.info(f"🚀 Starting Pixelmania Farm run (mode: {mode})...")
    config = load_config()
    db = load_database()

    accounts_meta = {}
    if os.path.exists(ACCOUNTS_DB_PATH):
        try:
            with open(ACCOUNTS_DB_PATH, "r", encoding="utf-8") as f:
                accounts_meta = json.load(f)
        except Exception:
            pass

    # Gather available session files
    valid_sessions = []
    if os.path.exists(SESSIONS_DIR):
        for fname in sorted(os.listdir(SESSIONS_DIR)):
            if fname.endswith(".session") and not fname.endswith(".session-journal"):
                acc_name = fname[:-8]
                sess_path = os.path.join(SESSIONS_DIR, fname)
                meta = accounts_meta.get(acc_name, {})
                valid_sessions.append((acc_name, sess_path, meta))

    if not valid_sessions:
        logger.warning("No sessions found for Pixelmania.")
        return {"status": "NO_SESSIONS", "processed": 0}

    logger.info(f"Loaded {len(valid_sessions)} accounts for Pixelmania.")

    batch_size = config.get("batch_size", 3)
    delay_min = config.get("delay_min", 2)
    delay_max = config.get("delay_max", 4)

    stats = {
        "total_accounts": len(valid_sessions),
        "success": 0,
        "failed": 0,
        "daily_claimed": 0,
        "tasks_claimed": 0,
        "pixels_mined": 0,
        "golden_found": 0,
        "start_time": datetime.utcnow().isoformat(),
        "end_time": None
    }

    for i in range(0, len(valid_sessions), batch_size):
        batch = valid_sessions[i:i + batch_size]
        batch_tasks = []
        for acc_name, sess_path, meta in batch:
            batch_tasks.append(run_single_account(acc_name, sess_path, meta, config))

        results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Pixelmania account error: {res}")
                stats["failed"] += 1
                continue

            acc_name = res.get("account")
            status = res.get("status")

            if status == "OK":
                stats["success"] += 1
                if res.get("daily_claimed"):
                    stats["daily_claimed"] += 1
                stats["tasks_claimed"] += res.get("tasks_claimed", 0)
                stats["pixels_mined"] += res.get("pixels_mined", 0)
                if res.get("golden_found"):
                    stats["golden_found"] += 1

                # Update database record using authoritative season_mined from server API
                prev_record = db.get(acc_name, {})
                prev_mined = prev_record.get("pixels_mined_total", 0)
                season_mined = res.get("season_mined", 0)
                actual_mined = max(prev_mined, season_mined, prev_mined + res.get("pixels_mined", 0))
                db[acc_name] = {
                    "account_name": acc_name,
                    "phone": res.get("phone", prev_record.get("phone")),
                    "stars": res.get("remaining_stars", 0),
                    "pixels_mined_total": actual_mined,
                    "golden_pixel_found": res.get("golden_found", False) or prev_record.get("golden_pixel_found", False),
                    "status": "ACTIVE",
                    "last_run": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                stats["failed"] += 1
                logger.warning(f"[{acc_name}] Pixelmania failed: {res.get('error')}")

        save_database(db)
        await asyncio.sleep(random.uniform(delay_min, delay_max))

    stats["end_time"] = datetime.utcnow().isoformat()
    logger.info(f"🏁 Pixelmania Farm run finished: {stats['success']}/{stats['total_accounts']} OK, {stats['pixels_mined']} pixels mined, {stats['golden_found']} golden found.")
    return stats

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_pixelmania_farm())
