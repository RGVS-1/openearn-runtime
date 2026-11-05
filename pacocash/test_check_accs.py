import asyncio
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from core.proxy_helper import get_working_proxy_for_account

async def check_acc(phone):
    with open('config.json') as f:
        config = json.load(f)
    
    s_file = None
    for f in os.listdir('sessions'):
        if phone in f and f.endswith('.session'):
            s_file = os.path.join('sessions', f)
            break
            
    if not s_file:
        print(f"Session for {phone} not found!")
        return
        
    p_info = get_working_proxy_for_account(f'chk_{phone}')
    proxy = p_info["telethon"] if p_info else None
    
    client = TelegramClient(
        s_file[:-8],
        config['api_id'],
        config['api_hash'],
        proxy=proxy,
        timeout=10.0,
        connection_retries=1
    )
    
    try:
        await client.connect()
        auth = await client.is_user_authorized()
        if auth:
            me = await client.get_me()
            print(f"[{phone}] ALIVE! {me.first_name} (@{me.username})")
        else:
            print(f"[{phone}] UNAUTHORIZED")
        await client.disconnect()
    except Exception as e:
        print(f"[{phone}] ERROR: {e}")

async def main():
    await check_acc('77474949897')
    await check_acc('77784244446')

if __name__ == '__main__':
    asyncio.run(main())
