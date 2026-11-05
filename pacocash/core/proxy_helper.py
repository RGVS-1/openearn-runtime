import os
import socket
import json
import time
import logging
from typing import Optional, Dict, Any, List, Set

logger = logging.getLogger("pacocash.proxy")

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "..", ".."))

RB_DIR = r"C:\Users\hoaki\Desktop\RB_Autimatic"
if os.path.exists(os.path.join(PROJECT_ROOT, "accounts_db.json")):
    ACCOUNTS_DB_FILE = os.path.join(PROJECT_ROOT, "accounts_db.json")
    PROXY_FILE = os.path.join(PROJECT_ROOT, "proxy.txt")
    DEAD_PROXIES_FILE = os.path.join(PROJECT_ROOT, "dead_proxies.json")
elif os.path.exists(os.path.join(RB_DIR, "accounts_db.json")):
    ACCOUNTS_DB_FILE = os.path.join(RB_DIR, "accounts_db.json")
    PROXY_FILE = os.path.join(RB_DIR, "proxy.txt")
    DEAD_PROXIES_FILE = os.path.join(RB_DIR, "dead_proxies.json")
else:
    ACCOUNTS_DB_FILE = "accounts_db.json"
    PROXY_FILE = "proxy.txt"
    DEAD_PROXIES_FILE = "dead_proxies.json"

# In-memory session cache of dead proxies
_DEAD_CACHE: Set[str] = set()

def is_socket_alive(host: str, port: int, timeout: float = 0.8) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, int(port)))
        s.close()
        return True
    except Exception:
        return False

def parse_proxy_line(line: str) -> Optional[dict]:
    parts = line.strip().split(":")
    if len(parts) == 4:
        ip, port, user, pwd = parts
        return {
            "raw": line.strip(),
            "ip": ip,
            "http_url": f"http://{user}:{pwd}@{ip}:{port}",
            "telethon": {
                "proxy_type": "http",
                "addr": ip,
                "port": int(port),
                "username": user,
                "password": pwd
            }
        }
    return None

def load_dead_proxies_set() -> Set[str]:
    """Loads all dead proxy entries (raw strings and IP addresses) from RB_Autimatic."""
    dead_set = set(_DEAD_CACHE)
    if os.path.exists(DEAD_PROXIES_FILE):
        try:
            with open(DEAD_PROXIES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k in data.keys():
                        dead_set.add(k)
                        dead_set.add(k.split(":")[0])
                elif isinstance(data, list):
                    for k in data:
                        dead_set.add(k)
                        dead_set.add(k.split(":")[0])
        except Exception as e:
            logger.debug(f"Error reading dead_proxies.json: {e}")
    return dead_set

def mark_proxy_dead(proxy_raw_or_ip: str) -> None:
    """Marks proxy as dead in RB_Autimatic/dead_proxies.json and in-memory cache."""
    if not proxy_raw_or_ip:
        return
    _DEAD_CACHE.add(proxy_raw_or_ip)
    ip = proxy_raw_or_ip.split(":")[0] if ":" in proxy_raw_or_ip else proxy_raw_or_ip
    _DEAD_CACHE.add(ip)

    try:
        cur_data = {}
        if os.path.exists(DEAD_PROXIES_FILE):
            try:
                with open(DEAD_PROXIES_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        cur_data = loaded
            except Exception:
                cur_data = {}

        cur_data[proxy_raw_or_ip] = time.time()
        with open(DEAD_PROXIES_FILE, "w", encoding="utf-8") as f:
            json.dump(cur_data, f, indent=2, ensure_ascii=False)
        logger.debug(f"[PROXY] Marked dead in RB_Autimatic: {proxy_raw_or_ip}")
    except Exception as e:
        logger.debug(f"[PROXY] Failed to write dead proxy {proxy_raw_or_ip}: {e}")

def load_alive_proxies(max_count: int = 30) -> List[dict]:
    """Reads proxy.txt from RB_Autimatic dynamically, filtering out all dead proxies."""
    if not os.path.exists(PROXY_FILE):
        return []
    
    dead_set = load_dead_proxies_set()
    alive = []
    try:
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        for l in lines:
            raw = l.strip()
            ip = raw.split(":")[0]
            if raw in dead_set or ip in dead_set:
                continue
            p = parse_proxy_line(raw)
            if p and is_socket_alive(p["ip"], p["telethon"]["port"], timeout=0.6):
                alive.append(p)
                if len(alive) >= max_count:
                    break
    except Exception as e:
        logger.error(f"Error loading alive proxies from RB_Autimatic: {e}")
    return alive

def is_proxy_valid(proxy_info: Optional[dict]) -> bool:
    """Checks if proxy is not marked dead and its port is accessible."""
    if not proxy_info or not isinstance(proxy_info, dict):
        return False
    raw = proxy_info.get("raw", "")
    ip = proxy_info.get("ip") or (raw.split(":")[0] if ":" in raw else "")
    dead_set = load_dead_proxies_set()
    if raw in dead_set or ip in dead_set:
        return False
    tp = proxy_info.get("telethon", {})
    addr = tp.get("addr") or ip
    port = tp.get("port")
    if not addr or not port:
        return False
    return is_socket_alive(addr, port, timeout=0.8)

def get_working_proxy_for_account(acc_name: str, meta: Optional[dict] = None, force_rotate: bool = False) -> Optional[dict]:
    """
    Returns a working proxy from RB_Autimatic for the given account.
    If current proxy is dead, 407, or force_rotate is True:
    - Marks previous proxy as dead
    - Pulls a fresh working proxy from RB_Autimatic proxy.txt
    - Saves it back to RB_Autimatic accounts_db.json and meta
    """
    proxy_info = meta.get("proxy") if isinstance(meta, dict) else None
    
    if not force_rotate and is_proxy_valid(proxy_info):
        return proxy_info

    # Mark dead if it had a proxy
    if proxy_info and isinstance(proxy_info, dict):
        dead_raw = proxy_info.get("raw") or proxy_info.get("ip")
        if dead_raw:
            mark_proxy_dead(dead_raw)

    # Find fresh candidate from RB_Autimatic
    alive_pool = load_alive_proxies(max_count=25)
    if not alive_pool:
        # Fallback to whatever proxy.txt has if none responded
        dead_set = load_dead_proxies_set()
        try:
            with open(PROXY_FILE, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            for l in lines:
                if l not in dead_set and l.split(":")[0] not in dead_set:
                    cand = parse_proxy_line(l)
                    if cand:
                        alive_pool.append(cand)
                        if len(alive_pool) >= 10: break
        except Exception:
            pass

    if not alive_pool:
        logger.warning(f"[PROXY] No working proxies found in {PROXY_FILE}")
        return proxy_info

    # Deterministic rotation based on account name
    new_proxy = alive_pool[abs(hash(acc_name + str(time.time() // 60))) % len(alive_pool)]

    # Update RB_Autimatic accounts_db.json
    if os.path.exists(ACCOUNTS_DB_FILE):
        try:
            with open(ACCOUNTS_DB_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
            if acc_name in db:
                db[acc_name]["proxy"] = new_proxy
                with open(ACCOUNTS_DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(db, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    if isinstance(meta, dict):
        meta["proxy"] = new_proxy

    logger.info(f"[PROXY] Account '{acc_name}' assigned fresh proxy from RB_Autimatic: {new_proxy.get('ip')}")
    return new_proxy
