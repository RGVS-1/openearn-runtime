import asyncio
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from core.proxy_helper import get_working_proxy_for_account

async def check():
    cfg = json.load(open('config.json', encoding='utf-8'))
    acc_db = json.load(open(r'C:\Users\hoaki\Desktop\RB_Autimatic\accounts_db.json', encoding='utf-8'))
    
    withdrawn_accs = [
        '[BY] Danila +375292302391 2025',
        '[KZ] Bekzat +77015616473 2019',
        '[BY] roman +375259792878 2024',
        '[UA] KIIIO +380998050189 2025'
    ]
    for acc in withdrawn_accs:
        meta = acc_db.get(acc, {})
        prx = get_working_proxy_for_account(acc, meta)
        client = TelegramClient(f'sessions/{acc}.session', cfg['api_id'], cfg['api_hash'], proxy=prx['telethon'])
        try:
            await client.connect()
            me = await client.get_entity('me')
            full = await client(GetFullUserRequest(me))
            bio = full.full_user.about or ''
            print(f'{acc}: bio="{bio}"')
            await client.disconnect()
        except Exception as e:
            print(f'{acc}: Error {e}')

if __name__ == '__main__':
    asyncio.run(check())
