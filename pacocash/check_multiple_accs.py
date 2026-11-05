import asyncio
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telethon import TelegramClient
from core.proxy_helper import get_working_proxy_for_account

async def check_account(session_file):
    with open('config.json') as f:
        config = json.load(f)

    p_info = get_working_proxy_for_account(os.path.basename(session_file))
    proxy = p_info["telethon"] if p_info else None

    client = TelegramClient(
        session_file[:-8],
        config['api_id'],
        config['api_hash'],
        proxy=proxy,
        timeout=10.0,
        connection_retries=1
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            print(f"[{os.path.basename(session_file)}] Unauthorized")
            return

        bot = await client.get_entity('PacoCashBot')
        await client.send_message(bot, "/start")
        await asyncio.sleep(2.0)
        msgs = await client.get_messages(bot, limit=2)
        start_msg = msgs[0]

        print(f"\n==================================================")
        print(f"ACCOUNT: {os.path.basename(session_file)}")
        print(f"==================================================")

        # Check u:pay:home
        for r in start_msg.reply_markup.rows:
            for b in r.buttons:
                if getattr(b, 'data', None) == b'u:pay:home':
                    await start_msg.click(data=b'u:pay:home')
                    await asyncio.sleep(2.0)
                    pay_msg = (await client.get_messages(bot, limit=1))[0]
                    print("--- [Заработок в чатах (u:pay:home)] ---")
                    print(pay_msg.text)
                    break

        # Check u:inv
        await client.send_message(bot, "/start")
        await asyncio.sleep(2.0)
        msgs = await client.get_messages(bot, limit=2)
        start_msg = msgs[0]
        for r in start_msg.reply_markup.rows:
            for b in r.buttons:
                if getattr(b, 'data', None) == b'u:inv':
                    await start_msg.click(data=b'u:inv')
                    await asyncio.sleep(2.0)
                    inv_msg = (await client.get_messages(bot, limit=1))[0]
                    print("\n--- [Пригласить друзей (u:inv)] ---")
                    print(inv_msg.text)
                    break

        await client.disconnect()
    except Exception as e:
        print(f"Error on {session_file}: {e}")

async def main():
    sessions_to_test = [
        r"C:\Users\hoaki\Desktop\RB_Autimatic\sessions\[RU] Xxxcalibur +79936124946 2025.session",
        r"C:\Users\hoaki\Desktop\RB_Autimatic\sessions\[KZ] UMAR +77474949897 2024.session",
        r"C:\Users\hoaki\Desktop\RB_Autimatic\sessions\[KZ] Шама +77774482820 2025.session",
        r"C:\Users\hoaki\Desktop\RB_Autimatic\sessions\[KZ] Artur +77786094250 2020.session"
    ]
    for s in sessions_to_test:
        if os.path.exists(s):
            await check_account(s)

if __name__ == '__main__':
    asyncio.run(main())
