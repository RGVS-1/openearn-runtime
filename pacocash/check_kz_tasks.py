import asyncio
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from core.proxy_helper import get_working_proxy_for_account

async def main():
    with open('config.json') as f:
        config = json.load(f)
    
    # Pick account from KZ that finished tasks 2 days ago
    phone_sub = '77074157140'
    session_file = None
    for f in os.listdir('sessions'):
        if phone_sub in f and f.endswith('.session'):
            session_file = os.path.join('sessions', f)
            break
            
    p_info = get_working_proxy_for_account('check_kz_tasks')
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
    bot = await client.get_entity('PacoCashBot')
    
    # Check tasks menu
    await client.send_message(bot, "/start")
    await asyncio.sleep(2)
    msgs = await client.get_messages(bot, limit=2)
    for r in msgs[0].reply_markup.rows:
        for b in r.buttons:
            if getattr(b, 'data', None) == b'u:tl:av:0':
                await msgs[0].click(data=b'u:tl:av:0')
                await asyncio.sleep(2)
                t_msgs = await client.get_messages(bot, limit=2)
                print("=== KZ TASKS MENU ===")
                print(t_msgs[0].text)
                
    # Check balance menu
    await client.send_message(bot, "/start")
    await asyncio.sleep(2)
    msgs = await client.get_messages(bot, limit=2)
    for r in msgs[0].reply_markup.rows:
        for b in r.buttons:
            if getattr(b, 'data', None) == b'u:bal:0':
                await msgs[0].click(data=b'u:bal:0')
                await asyncio.sleep(2)
                b_msgs = await client.get_messages(bot, limit=2)
                print("=== KZ BAL MENU ===")
                print(b_msgs[0].text)
                
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
