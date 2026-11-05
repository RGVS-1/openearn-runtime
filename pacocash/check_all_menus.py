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
    
    # Pick account Andrea USA or Kaz account
    session_file = None
    for f in os.listdir('sessions'):
        if '14314572694' in f and f.endswith('.session'):
            session_file = os.path.join('sessions', f)
            break
            
    if not session_file:
        for f in os.listdir('sessions'):
            if f.endswith('.session'):
                session_file = os.path.join('sessions', f)
                break
                
    print(f"Using session: {os.path.basename(session_file)}")
    p_info = get_working_proxy_for_account('check_all_menus')
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
    bot = await client.get_entity('PacoCashBot')
    
    # 1. Main menu /start
    print("\n--- 1. /start ---")
    await client.send_message(bot, "/start")
    await asyncio.sleep(2)
    msgs = await client.get_messages(bot, limit=2)
    start_msg = msgs[0]
    print(start_msg.text)
    
    # Print all buttons in main menu
    if start_msg.reply_markup and hasattr(start_msg.reply_markup, 'rows'):
        for r in start_msg.reply_markup.rows:
            for b in r.buttons:
                print(f"BTN: {b.text} -> data={getattr(b, 'data', None)} url={getattr(b, 'url', None)}")
                
    # 2. Check Tasks (u:tl:av:0)
    print("\n--- 2. Tasks menu (u:tl:av:0) ---")
    await start_msg.click(data=b'u:tl:av:0')
    await asyncio.sleep(2)
    task_msgs = await client.get_messages(bot, limit=2)
    for m in task_msgs:
        print(m.text)
        if m.reply_markup and hasattr(m.reply_markup, 'rows'):
            for r in m.reply_markup.rows:
                for b in r.buttons:
                    print(f"  TASK BTN: {b.text} -> data={getattr(b, 'data', None)} url={getattr(b, 'url', None)}")
                    
    # 3. Check Referral menu (u:inv)
    print("\n--- 3. Referral menu (u:inv) ---")
    await client.send_message(bot, "/start")
    await asyncio.sleep(2)
    msgs = await client.get_messages(bot, limit=2)
    for r in msgs[0].reply_markup.rows:
        for b in r.buttons:
            if getattr(b, 'data', None) == b'u:inv':
                await msgs[0].click(data=b'u:inv')
                await asyncio.sleep(2)
                inv_msgs = await client.get_messages(bot, limit=2)
                for im in inv_msgs:
                    print(im.text)
                    if im.reply_markup and hasattr(im.reply_markup, 'rows'):
                        for ir in im.reply_markup.rows:
                            for ib in ir.buttons:
                                print(f"  INV BTN: {ib.text} -> data={getattr(ib, 'data', None)} url={getattr(ib, 'url', None)}")
                                
    # 4. Check Balance menu (u:bal:0)
    print("\n--- 4. Balance menu (u:bal:0) ---")
    await client.send_message(bot, "/start")
    await asyncio.sleep(2)
    msgs = await client.get_messages(bot, limit=2)
    for r in msgs[0].reply_markup.rows:
        for b in r.buttons:
            if getattr(b, 'data', None) == b'u:bal:0':
                await msgs[0].click(data=b'u:bal:0')
                await asyncio.sleep(2)
                bal_msgs = await client.get_messages(bot, limit=2)
                for bm in bal_msgs:
                    print(bm.text)
                    if bm.reply_markup and hasattr(bm.reply_markup, 'rows'):
                        for br in bm.reply_markup.rows:
                            for bb in br.buttons:
                                print(f"  BAL BTN: {bb.text} -> data={getattr(bb, 'data', None)} url={getattr(bb, 'url', None)}")
                                
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
