import logging
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger("pacocash.referral_manager")

def get_referral_for_new_account(database: dict, config: dict) -> Tuple[str, str]:
    """
    Selects the optimal referral code for the next farm account:
    - If mode is 'single': always returns root referral code.
    - If mode is 'pyramid':
      1. First fills the Root account up to `root_target_referrals` (e.g., 4 accounts).
      2. Then finds the earliest completed farm account that has its own referral code
         and has invited fewer than `max_referrals_per_account` (e.g., 2 accounts).
      3. If no such account exists, falls back to Root.

    Returns:
        (referral_code, parent_account_label)
    """
    mode = config.get("referral_mode", "pyramid")
    root_code = config.get("referral_code", "riJVfpUUR")
    root_target = config.get("root_target_referrals", 4)
    max_per_acc = config.get("max_referrals_per_account", 2)

    if mode == "single":
        return root_code, "ROOT (Ваш основной аккаунт)"

    # Count how many direct referrals Root has
    root_children = [
        acc for acc, data in database.items()
        if data.get("parent_ref") == root_code
    ]

    if len(root_children) < root_target:
        return root_code, f"ROOT (Ваш основной аккаунт, слот {len(root_children)+1}/{root_target})"

    # Find earliest completed farm account needing referrals (excluding already withdrawn/archived)
    for acc_name, data in database.items():
        if data.get("status") != "COMPLETED":
            continue
        if data.get("withdrawn") or data.get("archived"):
            continue

        own_ref = data.get("own_ref_code")
        if not own_ref or own_ref == root_code:
            continue

        children = data.get("children", [])
        if len(children) < max_per_acc:
            slot_idx = len(children) + 1
            return own_ref, f"{acc_name} (Слот {slot_idx}/{max_per_acc})"

    # Fallback to Root
    return root_code, f"ROOT (Ваш основной аккаунт - fallback)"

def record_referral_success(database: dict, parent_code: str, child_account_name: str, root_code: str):
    """
    Updates the referral relationship and earnings in database.json.
    """
    # Find parent in database
    for acc_name, data in database.items():
        if data.get("own_ref_code") == parent_code:
            children = data.setdefault("children", [])
            if child_account_name not in children:
                children.append(child_account_name)
            data["referrals_count"] = len(children)
            data["referral_earned"] = round(len(children) * 0.50, 2)
            # Note: referral rewards are placed in 'Ожидает проверки' by PacoCashBot
            # and become available after the 48h verification period.
            break
