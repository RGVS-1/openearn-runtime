import os
import json
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("pacocash.session_manager")

# Resolve project root (where sessions/ and accounts_db.json reside)
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "..", ".."))

# Also support direct execution if root is cwd
if os.path.exists(os.path.join(PROJECT_ROOT, "sessions")):
    SESSIONS_DIR = os.path.join(PROJECT_ROOT, "sessions")
    ACCOUNTS_DB_PATH = os.path.join(PROJECT_ROOT, "accounts_db.json")
    CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")
elif os.path.exists("sessions"):
    SESSIONS_DIR = os.path.abspath("sessions")
    ACCOUNTS_DB_PATH = os.path.abspath("accounts_db.json")
    CONFIG_PATH = os.path.abspath("config.json")
else:
    SESSIONS_DIR = os.path.join(PROJECT_ROOT, "sessions")
    ACCOUNTS_DB_PATH = os.path.join(PROJECT_ROOT, "accounts_db.json")
    CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

PACO_DIR = os.path.abspath(os.path.join(_CURRENT_DIR, ".."))
DATABASE_FILE = os.path.join(PACO_DIR, "database.json")
WITHDRAWALS_FILE = os.path.join(PACO_DIR, "withdrawals.json")

def load_accounts_db() -> dict:
    if os.path.exists(ACCOUNTS_DB_PATH):
        try:
            with open(ACCOUNTS_DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading accounts_db.json from {ACCOUNTS_DB_PATH}: {e}")
    return {}

def load_database() -> dict:
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading database.json: {e}")
    return {}

def save_database(data: dict):
    try:
        with open(DATABASE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving database.json: {e}")

def get_canonical_sessions() -> List[Tuple[str, str, dict]]:
    """
    Returns all valid active accounts directly from the canonical sessions folder
    (tonopenrouter/sessions), matching Render cloud sessions.
    No session files are copied or deleted.
    """
    accounts_db = load_accounts_db()
    ready_accounts = []

    if not os.path.exists(SESSIONS_DIR):
        logger.warning(f"SESSIONS_DIR does not exist: {SESSIONS_DIR}")
        return []

    for fname in sorted(os.listdir(SESSIONS_DIR)):
        if fname.endswith(".session") and not fname.startswith("temp_"):
            acc_name = fname[:-8]
            sess_path = os.path.join(SESSIONS_DIR, fname)
            meta = accounts_db.get(acc_name, {})
            ready_accounts.append((acc_name, sess_path, meta))

    return ready_accounts

# Backwards compatibility alias for existing callers
sync_sessions = get_canonical_sessions
