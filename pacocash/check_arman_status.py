import asyncio
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from telethon.tl.functions.channels import GetParticipantRequest
from core.proxy_helper import get_working_proxy_for_account

async def main():
    with open('config.json') as f:
        config = json.load(f)
    
    phone_sub = '77784244446'
    session_file = None
    for f in os.listdir('sessions'):
        if phone_sub in f and f.endswith('.session'):
            session_file = os.path.join('sessions', f)
            break
            
    p_info = get_working_proxy_for_account('check_arman')
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
    print("Connected.")
    try:
        chat = await client.get_entity('ChatPaco')
        me = await client.get_me()
        p = await client(GetParticipantRequest(channel=chat, participant=me))
        print("Participant type:", type(p.participant))
        print("Participant details:", p.participant)
    except Exception as e:
        print("Participant check error:", e)
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
