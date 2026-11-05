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
            
    p_info = get_working_proxy_for_account('test_acc')
    proxy = p_info["telethon"] if p_info else None
    
    session_path = session_file[:-8]
    client = TelegramClient(
        session_path,
        config['api_id'],
        config['api_hash'],
        proxy=proxy,
        timeout=10.0,
        connection_retries=2
    )
    
    await client.connect()
    chat = await client.get_entity('ChatPaco')
    bot = await client.get_entity('PacoCashBot')
    
    # Send 2 messages with 10s delay
    print("Sending msg 1 (10s test)...")
    await client.send_message(chat, "кто в кости играет?")
    await asyncio.sleep(10)
    print("Sending msg 2 (10s test)...")
    await client.send_message(chat, "подскажите тактику")
    await asyncio.sleep(3)
    
    # Check stats
    msgs = await client.get_messages(bot, limit=5)
    for m in msgs:
        if m.reply_markup and hasattr(m.reply_markup, 'rows'):
            for r in m.reply_markup.rows:
                for b in r.buttons:
                    if getattr(b, 'data', None) == b'u:pay:home':
                        await m.click(data=b'u:pay:home')
                        await asyncio.sleep(2)
                        refreshed = await client.get_messages(bot, ids=m.id)
                        for line in refreshed.text.split('\n'):
                            if 'Сообщений' in line or 'Оплачено' in line:
                                print(line)
                        await client.disconnect()
                        return
                        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
