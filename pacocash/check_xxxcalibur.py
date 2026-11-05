import asyncio
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest
from core.proxy_helper import get_working_proxy_for_account

async def check():
    cfg = json.load(open('config.json', encoding='utf-8'))
    acc_db = json.load(open(r'C:\Users\hoaki\Desktop\RB_Autimatic\accounts_db.json', encoding='utf-8'))
    acc = '[RU] Xxxcalibur +79936124946 2025'
    meta = acc_db.get(acc, {})
    prx = get_working_proxy_for_account(acc, meta)
    client = TelegramClient(f'sessions/{acc}.session', cfg['api_id'], cfg['api_hash'], proxy=prx['telethon'])
    await client.connect()
    me = await client.get_entity('me')
    full = await client(GetFullUserRequest(me))
    bio = full.full_user.about or ""
    print(f"Xxxcalibur bio: '{bio}'")
    if bio:
        print("Clearing Xxxcalibur bio...")
        await client(UpdateProfileRequest(about=""))
        print("Xxxcalibur bio cleared!")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(check())
