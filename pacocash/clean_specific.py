import asyncio
import os
import json
from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

ALIVE_PRX = {"proxy_type": "http", "addr": "209.50.185.97", "port": 3129, "username": "5onpre5bnogl", "password": "d6j2zs75thtd7bl"}

async def clean_target(phone):
    cfg = json.load(open('config.json'))
    s = [f for f in os.listdir('sessions') if phone in f and f.endswith('.session')][0]
    client = TelegramClient(os.path.join('sessions', s[:-8]), cfg['api_id'], cfg['api_hash'], proxy=ALIVE_PRX, timeout=8.0)
    await client.connect()
    if await client.is_user_authorized():
        await client(UpdateProfileRequest(about=""))
        me = await client.get_me()
        full = await client(GetFullUserRequest(me))
        print(f"[{phone}] Verified clean bio: '{full.full_user.about}'")
    await client.disconnect()

async def main():
    for p in ['77774482820', '77474949897', '77758024545']:
        try:
            await clean_target(p)
        except Exception as e:
            print(f"[{p}] err: {e}")

asyncio.run(main())
