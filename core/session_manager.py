import os
import shutil
import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("openearn.session_manager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
TG_FARM_DIR = r"C:\Users\hoaki\Desktop\TG_farm"
RB_DIR = r"C:\Users\hoaki\Desktop\RB_Autimatic"
RB_SESSIONS_DIR = os.path.join(RB_DIR, "sessions")
RB_ACCOUNTS_DB = os.path.join(RB_DIR, "accounts_db.json")
RB_PROFILES = os.path.join(RB_DIR, "profiles.json")
DATABASE_FILE = os.path.join(BASE_DIR, "database.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_accounts_db() -> dict:
    if os.path.exists(RB_ACCOUNTS_DB):
        try:
            with open(RB_ACCOUNTS_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading accounts_db.json: {e}")
    return {}

def sync_sessions() -> List[Tuple[str, str, dict]]:
    """
    Syncs session files from RB_Autimatic/sessions into tonopenrouter/sessions.
    Ensures safe, isolated session copies with proper device metadata.
    Returns list of tuples: (account_name, session_path, account_metadata)
    """
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    accounts_db = load_accounts_db()

    farm_folders = set()
    if os.path.exists(TG_FARM_DIR):
        farm_folders = set(os.listdir(TG_FARM_DIR))

    profiles = {}
    if os.path.exists(RB_PROFILES):
        try:
            with open(RB_PROFILES, "r", encoding="utf-8") as f:
                profiles = json.load(f)
        except Exception:
            pass

    # Also check RB_SESSIONS_DIR
    if os.path.exists(RB_SESSIONS_DIR):
        for fname in os.listdir(RB_SESSIONS_DIR):
            if fname.endswith(".session"):
                a_name = fname[:-8]
                if (not farm_folders or a_name in farm_folders) and a_name not in profiles:
                    profiles[a_name] = os.path.join(RB_SESSIONS_DIR, fname)

    ready_accounts = []

    for acc_name, src_session in profiles.items():
        if farm_folders and acc_name not in farm_folders:
            continue
        if not os.path.exists(src_session):
            continue

        target_session = os.path.join(SESSIONS_DIR, f"{acc_name}.session")
        if not os.path.exists(target_session):
            try:
                shutil.copy2(src_session, target_session)
                logger.info(f"Copied clean session for {acc_name}")
            except Exception as e:
                logger.error(f"Could not copy session for {acc_name}: {e}")
                continue

        meta = accounts_db.get(acc_name, {})
        ready_accounts.append((acc_name, target_session, meta))

    logger.info(f"Total ready accounts synced: {len(ready_accounts)}")
    return ready_accounts
