import asyncio
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telethon import TelegramClient
from core.proxy_helper import get_working_proxy_for_account

async def main():
    with open('config.json') as f:
        config = json.load(f)

    # Let's check Danila or Xxxcalibur or another account
    session_file = None
    for f in os.listdir(r'C:\Users\hoaki\Desktop\RB_Autimatic\sessions'):
        if 'Danila' in f and f.endswith('.session'):
            session_file = os.path.join(r'C:\Users\hoaki\Desktop\RB_Autimatic\sessions', f)
            break

    if not session_file:
        for f in os.listdir(r'C:\Users\hoaki\Desktop\RB_Autimatic\sessions'):
            if f.endswith('.session'):
                session_file = os.path.join(r'C:\Users\hoaki\Desktop\RB_Autimatic\sessions', f)
                break

    print(f"Connecting with: {os.path.basename(session_file)}")
    p_info = get_working_proxy_for_account('live_check')
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

    bot = await client.get_entity('PacoCashBot')

    # 1. /start
    print("\n--- 1. Send /start ---")
    await client.send_message(bot, "/start")
    await asyncio.sleep(2.0)
    msgs = await client.get_messages(bot, limit=2)
    print(msgs[0].text)

    # 2. Click u:inv
    print("\n--- 2. Click [Пригласить друзей] (u:inv) ---")
    for r in msgs[0].reply_markup.rows:
        for b in r.buttons:
            if getattr(b, 'data', None) == b'u:inv':
                await msgs[0].click(data=b'u:inv')
                await asyncio.sleep(2.0)
                inv_msg = (await client.get_messages(bot, limit=1))[0]
                print(inv_msg.text)
                break

    # 3. Click u:pay:home
    print("\n--- 3. Click [Заработок в чатах] (u:pay:home) ---")
    await client.send_message(bot, "/start")
    await asyncio.sleep(2.0)
    msgs = await client.get_messages(bot, limit=2)
    for r in msgs[0].reply_markup.rows:
        for b in r.buttons:
            if getattr(b, 'data', None) == b'u:pay:home':
                await msgs[0].click(data=b'u:pay:home')
                await asyncio.sleep(2.0)
                pay_msg = (await client.get_messages(bot, limit=1))[0]
                print(pay_msg.text)
                break

    # 4. Click u:bal:0
    print("\n--- 4. Click [Баланс и вывод] (u:bal:0) ---")
    await client.send_message(bot, "/start")
    await asyncio.sleep(2.0)
    msgs = await client.get_messages(bot, limit=2)
    for r in msgs[0].reply_markup.rows:
        for b in r.buttons:
            if getattr(b, 'data', None) == b'u:bal:0':
                await msgs[0].click(data=b'u:bal:0')
                await asyncio.sleep(2.0)
                bal_msg = (await client.get_messages(bot, limit=1))[0]
                print(bal_msg.text)
                break

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
