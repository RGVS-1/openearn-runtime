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
    for jf in ["accounts_db.json", "database.json", "pixelmania_db.json", "mined_pixels.json", "pixelmania_config.json", "config.json", "jvault_accounts_state.json", "jvault_summary.json", "ton_wallets.json"]:
        full_p = os.path.join(BASE_DIR, jf)
        if os.path.exists(full_p):
            zf.write(full_p, jf)
            print(f"Packed {jf}")

    # 2. OpenEarn sessions
    sess_dir = os.path.join(BASE_DIR, "sessions")
    if os.path.exists(sess_dir):
        for f in os.listdir(sess_dir):
            if f.endswith(".session") or f.endswith(".json"):
                full_p = os.path.join(sess_dir, f)
                zf.write(full_p, os.path.join("sessions", f))


fernet = Fernet(key.encode("utf-8"))
enc_bytes = fernet.encrypt(buf.getvalue())

with open(output_vault, "wb") as f:
    f.write(enc_bytes)

print(f"[+] Successfully updated {output_vault} ({len(enc_bytes)} bytes) with AES-256 Fernet!")
