import asyncio
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest
from core.proxy_helper import get_working_proxy_for_account

async def main():
    with open('config.json') as f:
        config = json.load(f)
    
    phone_sub = '77474949897' # UMAR
    session_file = None
    for f in os.listdir('sessions'):
        if phone_sub in f and f.endswith('.session'):
            session_file = os.path.join('sessions', f)
            break
            
    p_info = get_working_proxy_for_account('chk_bio')
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
    print(f"Current about in Telegram: '{full.full_user.about}'")
    
    # Check exact bio string from bot
    bot = await client.get_entity('PacoCashBot')
    await client.send_message(bot, "/start")
    await asyncio.sleep(1)
    msgs = await client.get_messages(bot, limit=2)
    # Click u:pay:home
    for r in msgs[0].reply_markup.rows:
        for b in r.buttons:
            if getattr(b, 'data', None) == b'u:pay:home':
                await msgs[0].click(data=b'u:pay:home')
                await asyncio.sleep(2)
                break
                
    m_home = (await client.get_messages(bot, limit=1))[0]
    # find bio text in message
    print("Bot text snippet:")
    for line in m_home.text.split('\n'):
        if 'winpaco' in line.lower():
            print("Line from bot:", repr(line))
            target_phrase = line.replace('`', '').strip()
            print("Extracted target phrase:", repr(target_phrase))
            # Set this exact phrase!
            print("Updating profile with extracted target phrase...")
            await client(UpdateProfileRequest(about=target_phrase))
            await asyncio.sleep(2)
            
            # Click verify
            for r in m_home.reply_markup.rows:
                for b in r.buttons:
                    if getattr(b, 'data', None) == b'u:pay:bio':
                        await m_home.click(data=b'u:pay:bio')
                        await asyncio.sleep(2)
                        res = await client.get_messages(bot, limit=2)
                        print("Verification response:", res[0].text)
                        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
