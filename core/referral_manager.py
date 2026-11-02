import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("openearn.referral")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_FILE = os.path.join(BASE_DIR, "database.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

ROOT_REFERRAL_CODE = "ref_we4ses4p"
RECEIVER_ACCOUNT = "[RU] Xxxcalibur +79936124946 2025"

def get_referral_for_account(account_name: str, cfg: dict, db: dict) -> str:
    """
    Selects the referral code to use for a new account.
    - If mode is 'direct': always returns root referral code (Xxxcalibur).
    - If mode is 'pyramid': returns either root (until root_target_referrals reached)
      or the next available parent referral code in database.
    """
    mode = cfg.get("referral_mode", "direct").lower()
    root_code = cfg.get("referral_code", ROOT_REFERRAL_CODE)

    if mode == "direct":
        return root_code

    # Pyramid mode logic
    root_target = int(cfg.get("root_target_referrals", 5))
    max_per_child = int(cfg.get("max_referrals_per_account", 2))

    # Count how many direct refs root already has
    root_refs_count = 0
    child_ref_counts: Dict[str, int] = {}

    for name, data in db.items():
        ref_used = data.get("referral_used")
        if ref_used == root_code:
            root_refs_count += 1
        elif ref_used:
            child_ref_counts[ref_used] = child_ref_counts.get(ref_used, 0) + 1

    if root_refs_count < root_target:
        return root_code

    # Search for first child that has own referral code and haven't exceeded max_per_child
    for name, data in db.items():
        child_code = data.get("own_referral_code")
        if child_code and child_code != root_code:
            # Prefix 'ref_' if the code returned from API doesn't have it
            ref_param = child_code if child_code.startswith("ref_") else f"ref_{child_code}"
            used_cnt = child_ref_counts.get(ref_param, 0)
            if used_cnt < max_per_child:
                return ref_param

    # Fallback to root
    return root_code

def record_account_referral_info(account_name: str, ref_used: str, own_code: Optional[str], db: dict):
    if account_name not in db:
        db[account_name] = {}
    db[account_name]["referral_used"] = ref_used
    if own_code:
        clean_code = own_code if own_code.startswith("ref_") else f"ref_{own_code}"
        db[account_name]["own_referral_code"] = clean_code
