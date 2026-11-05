import asyncio
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from core.proxy_helper import get_working_proxy_for_account

async def inspect(phone):
    with open('config.json') as f:
        config = json.load(f)
    
    session_file = None
    for f in os.listdir('sessions'):
        if phone in f and f.endswith('.session'):
            session_file = os.path.join('sessions', f)
            break
            
    p_info = get_working_proxy_for_account(f'insp_{phone}')
    proxy = p_info["telethon"] if p_info else None
    
    client = TelegramClient(
        session_file[:-8],
        config['api_id'],
        config['api_hash'],
        proxy=proxy,
        timeout=10.0,
        connection_retries=1
    )
    
    await client.connect()
    me = await client.get_me()
    full = await client(GetFullUserRequest(me))
    print(f"[{phone}] First: '{me.first_name}', Last: '{me.last_name}', User: '@{me.username}', Bio: '{full.full_user.about}'")
    await client.disconnect()

async def main():
    await inspect('77774482820') # Succeeded
    await inspect('77474949897') # UMAR Failed

if __name__ == '__main__':
    asyncio.run(main())
