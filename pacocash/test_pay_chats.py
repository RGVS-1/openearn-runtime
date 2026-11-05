import asyncio
import sys
import io

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient
import os
import json
from core.proxy_helper import get_working_proxy_for_account

async def main():
    with open('config.json') as f:
        config = json.load(f)
    
    # Find session matching phone
    phone_sub = '77774482820'
    session_file = None
    for f in os.listdir('sessions'):
        if phone_sub in f and f.endswith('.session'):
            session_file = os.path.join('sessions', f)
            break
            
    if not session_file:
        print("Session not found!")
        return
        
    print(f"Using session: {os.path.basename(session_file)}")
    p_info = get_working_proxy_for_account('test_acc')
    proxy = p_info["telethon"] if p_info else None
    
    # Pass session path without .session extension to TelegramClient
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
    if not await client.is_user_authorized():
        print("Not authorized!")
        await client.disconnect()
        return
        
    print("Connected successfully!")
    me = await client.get_me()
    print(f"Me: {me.first_name} ({me.phone})")
    
    bot = await client.get_entity('PacoCashBot')
    
    # Click u:pay:chats or check messages
    messages = await client.get_messages(bot, limit=5)
    target_msg = None
    target_btn = None
    for msg in messages:
        if msg.reply_markup and hasattr(msg.reply_markup, 'rows'):
            for row in msg.reply_markup.rows:
                for btn in row.buttons:
                    if hasattr(btn, 'data') and btn.data == b'u:pay:chats':
                        target_msg = msg
                        target_btn = btn
                        break
    
    if target_msg:
        print("Found u:pay:chats button! Clicking...")
        await target_msg.click(data=b'u:pay:chats')
        await asyncio.sleep(2)
        new_msgs = await client.get_messages(bot, limit=3)
        for m in new_msgs:
            print("--- BOT MSG ---")
            print(m.text)
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        print(f"BTN: {b.text} -> {getattr(b, 'data', None)} / {getattr(b, 'url', None)}")
    else:
        print("u:pay:chats not found directly in last 5 messages, clicking u:pay:home first...")
        # find u:pay:home
        for msg in messages:
            if msg.reply_markup and hasattr(msg.reply_markup, 'rows'):
                for row in msg.reply_markup.rows:
                    for btn in row.buttons:
                        if hasattr(btn, 'data') and btn.data == b'u:pay:home':
                            await msg.click(data=b'u:pay:home')
                            await asyncio.sleep(2)
                            break
        
        # Now get messages again
        new_msgs = await client.get_messages(bot, limit=2)
        for m in new_msgs:
            if m.reply_markup and hasattr(m.reply_markup, 'rows'):
                for r in m.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, 'data', None) == b'u:pay:chats':
                            print("Clicking u:pay:chats...")
                            await m.click(data=b'u:pay:chats')
                            await asyncio.sleep(2)
                            res = await client.get_messages(bot, limit=2)
                            for rm in res:
                                print("--- CHATS MSG ---")
                                print(rm.text)
                                if rm.reply_markup and hasattr(rm.reply_markup, 'rows'):
                                    for rr in rm.reply_markup.rows:
                                        for bb in rr.buttons:
                                            print(f"BTN: {bb.text} -> {getattr(bb, 'data', None)} / {getattr(bb, 'url', None)}")
            
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
