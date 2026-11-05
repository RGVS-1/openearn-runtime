import os
import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("pacocash.wallets")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WALLETS_FILE = os.path.join(BASE_DIR, "wallets.json")

def load_wallets() -> dict:
    if os.path.exists(WALLETS_FILE):
        try:
            with open(WALLETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading wallets: {e}")
    return {}

def save_wallets(wallets: dict):
    with open(WALLETS_FILE, "w", encoding="utf-8") as f:
        json.dump(wallets, f, ensure_ascii=False, indent=4)

def generate_new_ton_wallet() -> Dict[str, Any]:
    """
    Generates a fresh TON Wallet v4r2 with 24-word mnemonic seed phrase.
    """
    from tonsdk.contract.wallet import Wallets, WalletVersionEnum
    from tonsdk.crypto import mnemonic_new

    words = mnemonic_new()
    mnemonics, pub_k, priv_k, wallet = Wallets.from_mnemonics(
        words, WalletVersionEnum.v4r2, workchain=0
    )
    # Bounceable friendly address (standard format EQ...)
    address_bounceable = wallet.address.to_string(True, True, True)
    # Non-bounceable friendly address (standard format UQ...)
    address_non_bounceable = wallet.address.to_string(True, True, False)
    # Raw address 0:...
    raw_address = wallet.address.to_string(False)

    return {
        "address": address_bounceable,
        "address_non_bounceable": address_non_bounceable,
        "raw_address": raw_address,
        "mnemonics": words,
        "mnemonic_str": " ".join(words),
        "public_key": pub_k.hex() if hasattr(pub_k, "hex") else str(pub_k),
        "private_key": priv_k.hex() if hasattr(priv_k, "hex") else str(priv_k),
        "wallet_version": "v4r2"
    }

def get_or_create_wallet_for_account(acc_name: str) -> Dict[str, Any]:
    """
    Ensures every account has its OWN unique TON wallet.
    Idempotent: if already exists, returns it; otherwise generates and saves.
    """
    wallets = load_wallets()
    if acc_name in wallets:
        return wallets[acc_name]

    new_wallet = generate_new_ton_wallet()
    wallets[acc_name] = new_wallet
    save_wallets(wallets)
    return new_wallet
