import asyncio
import json
import os
import sys
import socket
from datetime import datetime

# UTF-8 stdout/stderr handling for Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

API_ID = 32293468
API_HASH = "0897266f179723de0640905e2f7860f3"

RB_DIR = r"C:\Users\hoaki\Desktop\RB_Autimatic"
SESSIONS_DIR = os.path.join(RB_DIR, "sessions")
PROXY_FILE = os.path.join(RB_DIR, "proxy.txt")
ACCOUNTS_DB_FILE = os.path.join(RB_DIR, "accounts_db.json")
OUTPUT_REPORT = os.path.join(r"C:\Users\hoaki\Desktop\Pacocash", "clean_111_results.json")

def load_accounts_metadata() -> dict:
    if os.path.exists(ACCOUNTS_DB_FILE):
        try:
            with open(ACCOUNTS_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Warning reading accounts_db.json: {e}")
    return {}

def load_proxies() -> list:
    proxies = []
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                if len(parts) == 4:
                    ip, port, user, pwd = parts
                    proxies.append({
                        "raw": line,
                        "ip": ip,
                        "port": int(port),
                        "user": user,
                        "pass": pwd,
                        "telethon": {
                            "proxy_type": "http",
                            "addr": ip,
                            "port": int(port),
                            "username": user,
                            "password": pwd
                        }
                    })
    return proxies

async def test_proxy_socket(proxy: dict) -> bool:
    loop = asyncio.get_running_loop()
    def check():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.2)
            s.connect((proxy["ip"], proxy["port"]))
            s.close()
            return True
        except Exception:
            return False
    return await loop.run_in_executor(None, check)

async def filter_alive_proxies(proxies: list) -> list:
    print(f"[*] Testing {len(proxies)} proxies via socket...")
    tasks = [test_proxy_socket(p) for p in proxies]
    results = await asyncio.gather(*tasks)
    alive = [p for p, ok in zip(proxies, results) if ok]
    print(f"[+] Alive proxies: {len(alive)} / {len(proxies)}")
    return alive

proxy_cursor = 0
cursor_lock = asyncio.Lock()

async def get_next_proxy(alive_proxies: list) -> dict:
    global proxy_cursor
    async with cursor_lock:
        if not alive_proxies:
            return None
        p = alive_proxies[proxy_cursor % len(alive_proxies)]
        proxy_cursor += 1
        return p

async def process_account(session_file: str, accounts_db: dict, alive_proxies: list, sem: asyncio.Semaphore, idx: int, total: int) -> dict:
    acc_name = os.path.splitext(session_file)[0]
    session_full_path = os.path.join(SESSIONS_DIR, session_file)
    session_path_no_ext = session_full_path[:-8] # remove .session

    meta = accounts_db.get(acc_name, {})
    dev = meta.get("device", {
        "device_model": "Desktop",
        "system_version": "Windows 11 x64",
        "app_version": "4.16.8 x64",
        "system_lang_code": "ru-RU",
        "lang_code": "ru"
    })

    result = {
        "account": acc_name,
        "status": "UNKNOWN",
        "old_bio": "",
        "new_bio": "",
        "details": "",
        "proxy": ""
    }

    async with sem:
        client = None
        for attempt in range(3):
            proxy_info = await get_next_proxy(alive_proxies)
            tel_proxy = proxy_info["telethon"] if proxy_info else None
            proxy_str = proxy_info["raw"] if proxy_info else "NO_PROXY"
            result["proxy"] = proxy_str

            client = TelegramClient(
                session_path_no_ext,
                API_ID,
                API_HASH,
                proxy=tel_proxy,
                device_model=dev.get("device_model", "Desktop"),
                system_version=dev.get("system_version", "Windows 11 x64"),
                app_version=dev.get("app_version", "4.16.8 x64"),
                connection_retries=1,
                retry_delay=1,
                timeout=8.0,
                auto_reconnect=False
            )

            try:
                await asyncio.wait_for(client.connect(), timeout=10.0)
                if not await client.is_user_authorized():
                    await client.disconnect()
                    result["status"] = "UNAUTHORIZED"
                    result["details"] = "Session is unauthorized or revoked"
                    print(f"[{idx}/{total}] ❌ {acc_name} -> UNAUTHORIZED")
                    return result

                me = await client.get_entity('me')
                full = await client(GetFullUserRequest(me))
                current_bio = getattr(full.full_user, 'about', None) or ""
                result["old_bio"] = current_bio

                if current_bio.strip():
                    # Need to clean
                    await client(UpdateProfileRequest(about=""))
                    await asyncio.sleep(0.5)
                    # Verify
                    full_check = await client(GetFullUserRequest(me))
                    verified_bio = getattr(full_check.full_user, 'about', None) or ""
                    result["new_bio"] = verified_bio

                    if not verified_bio.strip():
                        result["status"] = "CLEARED"
                        result["details"] = f"Bio was: '{current_bio}' -> cleared to empty"
                        print(f"[{idx}/{total}] 🧹 {acc_name} -> CLEARED (was: '{current_bio[:30]}')")
                    else:
                        result["status"] = "FAILED_TO_CLEAR"
                        result["details"] = f"Bio still present: '{verified_bio}'"
                        print(f"[{idx}/{total}] ⚠️ {acc_name} -> FAILED TO CLEAR (still: '{verified_bio[:30]}')")
                else:
                    result["status"] = "ALREADY_EMPTY"
                    result["new_bio"] = ""
                    result["details"] = "Bio was already empty"
                    print(f"[{idx}/{total}] ⚪ {acc_name} -> ALREADY EMPTY")

                await client.disconnect()
                return result

            except Exception as e:
                err_msg = str(e)
                try:
                    await client.disconnect()
                except Exception:
                    pass

                # If connection/proxy error, retry with another proxy
                is_proxy_err = any(w in err_msg.lower() for w in [
                    "proxy", "timeout", "timed out", "connection reset", "socks", "407", "closed the connection"
                ])
                if is_proxy_err and attempt < 2:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    result["status"] = "ERROR"
                    result["details"] = err_msg
                    print(f"[{idx}/{total}] ⚠️ {acc_name} -> ERROR: {err_msg[:60]}")
                    return result

    return result

async def main():
    print("=" * 70)
    print("🚀 STARTING COMPLETE BIO CLEANUP FOR ALL 111 RB_AUTOMATIC / TG_FARM ACCOUNTS")
    print("=" * 70)

    if not os.path.exists(SESSIONS_DIR):
        print(f"[-] ERROR: Sessions directory not found: {SESSIONS_DIR}")
        return

    session_files = sorted([f for f in os.listdir(SESSIONS_DIR) if f.endswith(".session")])
    print(f"[*] Found {len(session_files)} sessions in {SESSIONS_DIR}")

    if len(session_files) != 111:
        print(f"[!] Warning: expected 111 sessions, but found {len(session_files)}")

    accounts_db = load_accounts_metadata()
    print(f"[*] Loaded metadata for {len(accounts_db)} accounts from accounts_db.json")

    all_proxies = load_proxies()
    alive_proxies = await filter_alive_proxies(all_proxies)

    if not alive_proxies:
        print("[-] ERROR: No alive proxies found!")
        return

    sem = asyncio.Semaphore(5) # 5 concurrent connections to stay safe with Telegram rate limits
    total = len(session_files)

    tasks = [
        process_account(s_file, accounts_db, alive_proxies, sem, i + 1, total)
        for i, s_file in enumerate(session_files)
    ]

    start_time = datetime.now()
    results = await asyncio.gather(*tasks)
    elapsed = (datetime.now() - start_time).total_seconds()

    # Summarize
    cleared = [r for r in results if r["status"] == "CLEARED"]
    already_empty = [r for r in results if r["status"] == "ALREADY_EMPTY"]
    unauthorized = [r for r in results if r["status"] == "UNAUTHORIZED"]
    errors = [r for r in results if r["status"] in ("ERROR", "FAILED_TO_CLEAR", "UNKNOWN")]

    print("\n" + "=" * 70)
    print("📊 FINAL SUMMARY")
    print("=" * 70)
    print(f"Total Accounts Processed: {total}")
    print(f"🧹 Successfully Cleared:   {len(cleared)}")
    print(f"⚪ Already Empty:          {len(already_empty)}")
    print(f"❌ Unauthorized / Dead:   {len(unauthorized)}")
    print(f"⚠️ Errors / Retries needed:{len(errors)}")
    print(f"⏱️ Time taken:             {elapsed:.1f} seconds")
    print("=" * 70)

    # Save to JSON
    summary_data = {
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "cleared_count": len(cleared),
        "already_empty_count": len(already_empty),
        "unauthorized_count": len(unauthorized),
        "error_count": len(errors),
        "elapsed_seconds": elapsed,
        "results": results
    }

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    print(f"[+] Detailed report saved to: {OUTPUT_REPORT}")

if __name__ == "__main__":
    asyncio.run(main())
