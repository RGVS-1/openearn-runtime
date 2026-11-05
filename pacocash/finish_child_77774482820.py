import asyncio
import sys
import os
import random
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from core.proxy_helper import get_working_proxy_for_account

MESSAGES_POOL = [
    "ку всем", "привет", "как настроение народ?", "сегодня кто вывел?", 
    "пако нормальная тема", "кто в кости поднял?", "я пока по мелочи", 
    "розыгрыш сегодня в 21:00 как обычно?", "удачи всем в конкурсе", 
    "кто-то выводил на криптобота?", "моментально приходит?", "норм тема", 
    "ждем розыгрыш", "всем профита", "фарту масти", "сегодня удачный день", 
    "а сколько в среднем вывод идет?", "минута где-то?", "ого быстро", "топчик", 
    "кто сколько за день поднял?", "красава", "давай тащи", "жестко", 
    "в рулетку кто играет?", "ставки чисто по фану", "главное не азартить сильно", 
    "ну чисто для розыгрыша пишу", "51 смс набить недолго", "чат живой прям", 
    "всем доброго вечера", "погнали", "плюс", "го", "у кого какой баланс?", 
    "пако платит проверено", "хорош", "держите в курсе", "фарта", "увидимся на розыгрыше",
    "всем привет кто тут", "вечер в хату", "надеюсь сегодня повезет", "кто фаворит в чате?",
    "всем зеленых свечей", "пако бот крутой", "баланс капает потихоньку", "у кого сколько сообщений уже?",
    "на криптобот чеком выводят?", "давно в пако играете?", "радует что без задержек", "всем удачи"
]

async def check_stats(client, bot):
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
                        refreshed = await client.get_messages(bot, ids=m.id)
                        paid = 0
                        recv = 0
                        for line in refreshed.text.split('\n'):
                            if 'Сообщений получено:' in line:
                                recv = int(line.split('**')[1])
                            if 'Оплачено:' in line:
                                paid = int(line.split('**')[1])
                        return recv, paid, refreshed.text
    return 0, 0, ""

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
    chat = await client.get_entity('ChatPaco')
    bot = await client.get_entity('PacoCashBot')
    
    recv, paid, _ = await check_stats(client, bot)
    print(f"Starting stats: Received={recv}, Paid={paid}")
    
    needed = 51 - paid
    print(f"Messages needed to reach 51: {needed}")
    
    pool = list(MESSAGES_POOL)
    random.shuffle(pool)
    
    sent = 0
    idx = 0
    while paid < 51:
        msg = pool[idx % len(pool)]
        idx += 1
        print(f"[{sent+1}/{needed}] Sending: '{msg}' (Current paid: {paid})...")
        try:
            await client.send_message(chat, msg)
        except Exception as e:
            print(f"Send error: {e}")
            await asyncio.sleep(5)
            continue
            
        sent += 1
        # Random delay between 9 and 13 seconds (slowmode is 5s)
        delay = random.uniform(9.5, 12.5)
        await asyncio.sleep(delay)
        
        # Every 10 messages, verify progress in bot
        if sent % 10 == 0:
            recv, paid, _ = await check_stats(client, bot)
            print(f"--> Progress check: Received={recv}, Paid={paid}/51")
            
    # Final check
    recv, paid, text = await check_stats(client, bot)
    print(f"FINISHED! Final stats: Received={recv}, Paid={paid}")
    print(text[:300])
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
