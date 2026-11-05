import asyncio
import sys
import os
import random
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
            
    p_info = get_working_proxy_for_account('child_77774482820')
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
    print("Connected.", flush=True)
    chat = await client.get_entity('ChatPaco')
    bot = await client.get_entity('PacoCashBot')
    
    phrases = [
        "скоро 21:00 жду розыгрыш",
        "всем удачи сегодня пацаны",
        "пако топ проект",
        "надеюсь выиграть хоть раз",
        "всем профита и хорошего вечера"
    ]
    
    for i, p in enumerate(phrases, 1):
        print(f"[{i}/5] Sending: '{p}'...", flush=True)
        await client.send_message(chat, p)
        await asyncio.sleep(11)
        
    print("All 5 sent! Checking PacoCashBot stats...", flush=True)
    await client.send_message(bot, "/start")
    await asyncio.sleep(2)
    msgs = await client.get_messages(bot, limit=3)
    for m in msgs:
        if m.reply_markup and hasattr(m.reply_markup, 'rows'):
            for r in m.reply_markup.rows:
                for b in r.buttons:
                    if getattr(b, 'data', None) == b'u:pay:home':
                        await m.click(data=b'u:pay:home')
                        await asyncio.sleep(3)
                        refreshed = await client.get_messages(bot, ids=m.id)
                        print("=== FINAL 51 STATS ===", flush=True)
                        print(refreshed.text, flush=True)
                        break
                        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
