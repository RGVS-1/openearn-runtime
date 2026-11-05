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
    
    # Pick a fresh account that can read ChatPaco
    session_file = None
    for f in os.listdir('sessions'):
        if '14314572694' in f and f.endswith('.session'):
            session_file = os.path.join('sessions', f)
            break
            
    p_info = get_working_proxy_for_account('chat_reader')
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
    
    try:
        chat = await client.get_entity('ChatPaco')
        print(f"Chat: {chat.title} (id={chat.id})")
        
        # Get last 50 messages
        msgs = await client.get_messages(chat, limit=50)
        print(f"Fetched {len(msgs)} messages from ChatPaco:")
        human_texts = []
        for m in msgs:
            # Skip bot messages
            if m.sender and getattr(m.sender, 'bot', False):
                continue
            if m.text and len(m.text.strip()) > 0:
                sender_name = getattr(m.sender, 'first_name', 'Anon') if m.sender else 'Anon'
                txt = m.text.replace('\n', ' ')
                print(f"[{sender_name}]: {txt}")
                human_texts.append(txt)
                
        with open('chat_sample.json', 'w', encoding='utf-8') as f:
            json.dump(human_texts, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print("Error reading chat:", e)
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
