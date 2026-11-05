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
    
    phone_sub = '77774482820'
    session_file = None
    for f in os.listdir('sessions'):
        if phone_sub in f and f.endswith('.session'):
            session_file = os.path.join('sessions', f)
            break
            
    p_info = get_working_proxy_for_account('test_77774482820')
    proxy = p_info["telethon"] if p_info else None
    
    client = TelegramClient(
        session_file[:-8],
        config['api_id'],
        config['api_hash'],
        proxy=proxy,
        timeout=10.0,
        connection_retries=2
    )
    
    await client.connect()
    chat = await client.get_entity('ChatPaco')
    bot = await client.get_entity('PacoCashBot')
    
    # Check stats first
    await client.send_message(bot, "/start")
    await asyncio.sleep(2)
    msgs = await client.get_messages(bot, limit=3)
    for m in msgs:
        if m.reply_markup and hasattr(m.reply_markup, 'rows'):
            for r in m.reply_markup.rows:
                for b in r.buttons:
                    if getattr(b, 'data', None) == b'u:pay:home':
                        await m.click(data=b'u:pay:home')
                        await asyncio.sleep(2)
                        refreshed = await client.get_messages(bot, ids=m.id)
                        print("=== CURRENT STATS ===")
                        for l in refreshed.text.split('\n'):
                            if 'Сообщений' in l or 'Оплачено' in l or 'Розыгрыш' in l:
                                print(l)
                                
    # Try sending 1 message to ChatPaco
    try:
        print("Testing sending 1 message to ChatPaco...")
        await client.send_message(chat, "всем доброй ночи")
        print("SUCCESSFULLY SENT MESSAGE TO CHATPACO!")
    except Exception as e:
        print("SEND ERROR:", e)
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
