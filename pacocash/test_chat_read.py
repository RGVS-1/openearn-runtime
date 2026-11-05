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
    print("Chat:", chat.title, chat.username)
    
    # Get last 10 messages from chat
    messages = await client.get_messages(chat, limit=10)
    for m in messages:
        sender_name = getattr(m.sender, 'first_name', '') if m.sender else ''
        print(f"[{sender_name}]: {m.text[:60] if m.text else '<media>'}")
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
