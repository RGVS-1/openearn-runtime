import os
import io
import zipfile
import json
from cryptography.fernet import Fernet

BASE_DIR = r"C:\Users\hoaki\Desktop\tonopenrouter"
vault_key_path = os.path.join(BASE_DIR, "vault_key.txt")
with open(vault_key_path, "r", encoding="utf-8") as f:
    key = f.read().strip()

output_vault = os.path.join(BASE_DIR, "vault.enc")

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    # 1. Root JSON files
    for jf in [
        "accounts_db.json", "database.json", "pixelmania_db.json", "mined_pixels.json",
        "pixelmania_config.json", "config.json", "jvault_accounts_state.json",
        "jvault_summary.json", "ton_wallets.json", "pacocash_summary.json", "promos_history.json", "pacocash_clean_pool.json"
    ]:
        full_p = os.path.join(BASE_DIR, jf)
        if os.path.exists(full_p):
            zf.write(full_p, jf)
            print(f"Packed {jf}")

    # 2. PacoCash directory (core, database, withdrawals, config)
    paco_dir = os.path.join(BASE_DIR, "pacocash")
    if os.path.exists(paco_dir):
        for root, dirs, files in os.walk(paco_dir):
            if "__pycache__" in root or "sessions" in root or "archived_sessions" in root:
                continue
            for f in files:
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, BASE_DIR)
                zf.write(full_p, rel_p)
                print(f"Packed {rel_p}")

    # 3. Sessions (all 113 canonical sessions)
    sess_dir = os.path.join(BASE_DIR, "sessions")
    if os.path.exists(sess_dir):
        for f in os.listdir(sess_dir):
            if (f.endswith(".session") or f.endswith(".json")) and not f.startswith("temp_"):
                full_p = os.path.join(sess_dir, f)
                zf.write(full_p, os.path.join("sessions", f))

fernet = Fernet(key.encode("utf-8"))
enc_bytes = fernet.encrypt(buf.getvalue())

with open(output_vault, "wb") as f:
    f.write(enc_bytes)

print(f"[+] Successfully updated {output_vault} ({len(enc_bytes)} bytes) with AES-256 Fernet!")
