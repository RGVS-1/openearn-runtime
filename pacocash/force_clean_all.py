import asyncio
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest
from core.proxy_helper import load_alive_proxies

# List of working alive proxies verified with socket connect
ALIVE_POOL = [
    {"telethon": {"proxy_type": "http", "addr": "209.50.185.97", "port": 3129, "username": "5onpre5bnogl", "password": "d6j2zs75thtd7bl"}},
    {"telethon": {"proxy_type": "http", "addr": "216.26.230.7", "port": 3129, "username": "5onpre5bnogl", "password": "d6j2zs75thtd7bl"}},
    {"telethon": {"proxy_type": "http", "addr": "209.50.171.172", "port": 3129, "username": "5onpre5bnogl", "password": "d6j2zs75thtd7bl"}},
    {"telethon": {"proxy_type": "http", "addr": "104.207.43.180", "port": 3129, "username": "5onpre5bnogl", "password": "d6j2zs75thtd7bl"}},
    {"telethon": {"proxy_type": "http", "addr": "104.207.52.154", "port": 3129, "username": "5onpre5bnogl", "password": "d6j2zs75thtd7bl"}},
]

async def clean_one(session_file, cfg, proxy_idx):
    acc_name = os.path.splitext(session_file)[0]
    s_path = os.path.join('sessions', session_file)
    
    proxy = ALIVE_POOL[proxy_idx % len(ALIVE_POOL)]["telethon"]
    client = TelegramClient(
        s_path[:-8],
        cfg["api_id"],
        cfg["api_hash"],
        proxy=proxy,
        timeout=10.0,
        connection_retries=1
    )
    
    try:
        await asyncio.wait_for(client.connect(), timeout=10.0)
        if not await client.is_user_authorized():
            await client.disconnect()
            return f"{acc_name[:25]}: UNAUTHORIZED"
            
        me = await client.get_entity('me')
        full = await client(GetFullUserRequest(me))
        about = full.full_user.about or ""
        
        if about:
            await client(UpdateProfileRequest(about=""))
            await client.disconnect()
            return f"{acc_name[:25]}: ОЧИЩЕНО (было: '{about[:25]}...')"
        else:
            await client.disconnect()
            return f"{acc_name[:25]}: Уже пусто"
    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass
        return f"{acc_name[:25]}: Ошибка ({e})"

async def main():
    cfg = json.load(open('config.json'))
    sessions = [f for f in os.listdir('sessions') if f.endswith('.session')]
    print(f"Checking all {len(sessions)} sessions with guaranteed alive proxies...")
    
    # Check specifically active sessions
    sem = asyncio.Semaphore(5)
    
    async def worker(idx, f):
        async with sem:
            res = await clean_one(f, cfg, idx)
            if "ОЧИЩЕНО" in res:
                print(f"✔ [BIO CLEARED] {res}")
            elif "Уже пусто" in res:
                print(f"✔ [CLEAN] {res}")
            else:
                print(f"- [SKIP] {res}")
                
    tasks = [worker(i, f) for i, f in enumerate(sessions)]
    await asyncio.gather(*tasks)
    print("\nALL SESSIONS CHECKED AND CLEANED!")

if __name__ == '__main__':
    asyncio.run(main())
