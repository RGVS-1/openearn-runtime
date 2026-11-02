import os
import socket
import json
import time
import logging
from typing import Optional, Dict, Any, List, Set

logger = logging.getLogger("openearn.proxy")

RB_DIR = r"C:\Users\hoaki\Desktop\RB_Autimatic"
PROXY_FILE = os.path.join(RB_DIR, "proxy.txt")
DEAD_PROXIES_FILE = os.path.join(RB_DIR, "dead_proxies.json")
ACCOUNTS_DB_FILE = os.path.join(RB_DIR, "accounts_db.json")

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
        logger.error(f"Error loading alive proxies: {e}")
    return alive

def is_proxy_valid(proxy_info: Optional[dict]) -> bool:
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
    proxy_info = meta.get("proxy") if isinstance(meta, dict) else None

    if not force_rotate and is_proxy_valid(proxy_info):
        return proxy_info

    if proxy_info:
        raw = proxy_info.get("raw")
        if raw:
            mark_proxy_dead(raw)

    alive_proxies = load_alive_proxies(max_count=20)
    if not alive_proxies:
        logger.warning(f"No alive backup proxies found in {PROXY_FILE}")
        return None

    new_proxy = alive_proxies[0]
    logger.info(f"Assigning new working proxy {new_proxy['raw']} to {acc_name}")

    if isinstance(meta, dict):
        meta["proxy"] = new_proxy

    if os.path.exists(ACCOUNTS_DB_FILE):
        try:
            with open(ACCOUNTS_DB_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
            if acc_name in db:
                db[acc_name]["proxy"] = new_proxy
                with open(ACCOUNTS_DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(db, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to update accounts_db with new proxy for {acc_name}: {e}")

    return new_proxy
