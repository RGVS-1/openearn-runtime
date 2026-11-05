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
    
    # Pick a fresh account, e.g. one from USA or a fresh Kazakhstan account
    # that has NEVER touched ChatPaco!
    session_file = None
    for f in os.listdir('sessions'):
        if '14314572694' in f and f.endswith('.session'): # Andrea USA
            session_file = os.path.join('sessions', f)
            break
            
    if not session_file:
        for f in os.listdir('sessions'):
            if f.endswith('.session'):
                session_file = os.path.join('sessions', f)
                break
                
    print(f"Using session: {os.path.basename(session_file)}")
    p_info = get_working_proxy_for_account('fresh_check')
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
    if not await client.is_user_authorized():
        print("Unauthorized")
        return
        
    try:
        chat = await client.get_entity('ChatPaco')
        print(f"Chat found! Title: '{chat.title}', Username: '{chat.username}'")
        # Check chat permissions
        if hasattr(chat, 'default_banned_rights'):
            print("Default banned rights:", chat.default_banned_rights)
    except Exception as e:
        print("Error getting ChatPaco entity:", e)
        
    # Also check PacoCashBot u:pay:chats to see if the link changed!
    try:
        bot = await client.get_entity('PacoCashBot')
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
                            break
        msgs2 = await client.get_messages(bot, limit=2)
        for m in ms2:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, 'data', None) == b'u:pay:chats':
                            await m.click(data=b'u:pay:chats')
                            await asyncio.sleep(2)
                            break
        msgs3 = await client.get_messages(bot, limit=2)
        print("=== BOT CHATS MENU ===")
        for m in msgs3:
            print(m.text)
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        print(f"BTN: {b.text} -> {getattr(b, 'data', None)} / {getattr(b, 'url', None)}")
    except Exception as e:
        print("Bot check error:", e)
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
