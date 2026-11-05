import asyncio
import os
import sys
import json
import logging
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from rich.console import Console
from rich.table import Table
from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.errors.common import AuthKeyNotFound

from core.proxy_helper import get_working_proxy_for_account

console = Console()
CONFIG_FILE = "config.json"
DATABASE_FILE = "database.json"
ACCOUNTS_DB_FILE = r"C:\Users\hoaki\Desktop\RB_Autimatic\accounts_db.json"
BIO_TEXT = "@winpaco — free case every day!"

async def fix_account_bio_and_task(client: TelegramClient, acc_name: str) -> dict:
    """
    1. Sets bio to '@winpaco — free case every day!'
    2. Navigates to PacoCashBot tasks -> violations
    3. Resets and checks pripiska task if violation exists
    4. If not in violations, checks available tasks and accepts if present
    """
    # 1. Update Bio
    try:
        await client(UpdateProfileRequest(about=BIO_TEXT))
    except Exception as e:
        return {"ok": False, "error": f"Ошибка установки био: {e}"}

    await asyncio.sleep(1.5)

    # 2. Check PacoCashBot
    try:
        await client.send_message("PacoCashBot", "/start")
        await asyncio.sleep(2)

        # Click Tasks (u:tl:av:0)
        msgs = await client.get_messages("PacoCashBot", limit=1)
        if not msgs:
            return {"ok": True, "details": "Био установлено, бот не ответил на /start"}
        
        try:
            await msgs[0].click(data=b'u:tl:av:0')
            await asyncio.sleep(1.8)
        except Exception:
            pass

        # Click History (u:tl:chk:0)
        msgs = await client.get_messages("PacoCashBot", limit=1)
        try:
            await msgs[0].click(data=b'u:tl:chk:0')
            await asyncio.sleep(1.8)
        except Exception:
            pass

        # Click Violations (u:tl:bad:0)
        msgs = await client.get_messages("PacoCashBot", limit=1)
        try:
            await msgs[0].click(data=b'u:tl:bad:0')
            await asyncio.sleep(1.8)
        except Exception:
            pass

        # Check for violation item
        msgs = await client.get_messages("PacoCashBot", limit=1)
        pripiska_btn = None
        if msgs and msgs[0].reply_markup:
            for r in msgs[0].reply_markup.rows:
                for b in r.buttons:
                    if getattr(b, 'data', None) and b.data.startswith(b'u:p:'):
                        pripiska_btn = b.data
                        break
                if pripiska_btn:
                    break

        if pripiska_btn:
            # Click into violation
            await msgs[0].click(data=pripiska_btn)
            await asyncio.sleep(2)

            m_det = (await client.get_messages("PacoCashBot", limit=1))[0]
            rst_btn = None
            if m_det.reply_markup:
                for r in m_det.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, 'data', None) and b.data.startswith(b'u:rst:'):
                            rst_btn = b.data
                            break
                    if rst_btn:
                        break

            if rst_btn:
                await m_det.click(data=rst_btn)
                await asyncio.sleep(2)

                m_chk = (await client.get_messages("PacoCashBot", limit=1))[0]
                chk_btn = None
                if m_chk.reply_markup:
                    for r in m_chk.reply_markup.rows:
                        for b in r.buttons:
                            if getattr(b, 'data', None) and b.data.startswith(b'u:chk:'):
                                chk_btn = b.data
                                break
                        if chk_btn:
                            break

                if chk_btn:
                    await m_chk.click(data=chk_btn)
                    await asyncio.sleep(2)
                    return {"ok": True, "details": "Био установлено + нарушение сброшено и проверено (🟡 на проверке)"}

            return {"ok": True, "details": "Био установлено + нарушение найдено, кнопка сброса отработала"}

        # If not in violations, check if in available tasks
        try:
            await msgs[0].click(data=b'u:tl:av:0')
            await asyncio.sleep(1.8)
            m_av = (await client.get_messages("PacoCashBot", limit=1))[0]
            if m_av.reply_markup:
                for r in m_av.reply_markup.rows:
                    for b in r.buttons:
                        if getattr(b, 'data', None) == b'u:t:6':
                            await m_av.click(data=b'u:t:6')
                            await asyncio.sleep(1.8)
                            m_acc = (await client.get_messages("PacoCashBot", limit=1))[0]
                            await m_acc.click(data=b'u:acc:6')
                            await asyncio.sleep(1.8)
                            m_val = (await client.get_messages("PacoCashBot", limit=1))[0]
                            await m_val.click(data=b'u:chk:6')
                            await asyncio.sleep(1.8)
                            return {"ok": True, "details": "Био установлено + задание принято и отправлено на проверку"}
        except Exception:
            pass

        return {"ok": True, "details": "Био установлено (задание уже активно или выполнено)"}
    except Exception as e:
        return {"ok": True, "details": f"Био установлено, ошибка интерфейса бота: {e}"}

async def main():
    console.print("\n[bold cyan]══════════════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold yellow]  ⚡ ВОССТАНОВЛЕНИЕ БИО И СНЯТИЕ НАРУШЕНИЙ НА ВСЕХ АККАУНТАХ ФЕРМЫ[/bold yellow]")
    console.print("[bold cyan]══════════════════════════════════════════════════════════════════[/bold cyan]\n")

    if not os.path.exists(CONFIG_FILE) or not os.path.exists(DATABASE_FILE):
        console.print("[bold red]Файлы конфигурации или базы данных не найдены![/bold red]")
        return

    cfg = json.load(open(CONFIG_FILE, "r", encoding="utf-8"))
    db = json.load(open(DATABASE_FILE, "r", encoding="utf-8"))
    acc_db = json.load(open(ACCOUNTS_DB_FILE, "r", encoding="utf-8")) if os.path.exists(ACCOUNTS_DB_FILE) else {}

    # Target unwithdrawn accounts that are not yet fixed
    targets = [k for k, v in db.items() if not v.get("withdrawn") and not v.get("bio_fixed")]
    console.print(f"Всего аккаунтов для обработки: [bold green]{len(targets)}[/bold green]\n")

    success_count = 0
    fail_count = 0

    for idx, acc_name in enumerate(targets, 1):
        s_file = f"sessions/{acc_name}.session"
        if not os.path.exists(s_file):
            continue

        meta = acc_db.get(acc_name, {})
        prx = get_working_proxy_for_account(acc_name, meta)
        prx_ip = prx["telethon"]["addr"] if prx and "telethon" in prx else "direct"

        console.print(f"[{idx}/{len(targets)}] Обработка [bold yellow]{acc_name}[/bold yellow] (Proxy: {prx_ip})...", end=" ")

        client = TelegramClient(
            s_file,
            cfg["api_id"],
            cfg["api_hash"],
            proxy=prx["telethon"] if prx else None,
            connection_retries=2,
            retry_delay=1
        )

        try:
            await asyncio.wait_for(client.connect(), timeout=12.0)
            if not await client.is_user_authorized():
                console.print("[red]✖ Сессия не авторизована[/red]")
                fail_count += 1
                continue

            res = await fix_account_bio_and_task(client, acc_name)
            if res.get("ok"):
                console.print(f"[bold green]✔[/bold green] [dim]{res.get('details')}[/dim]")
                db[acc_name]["bio_fixed"] = True
                success_count += 1
            else:
                console.print(f"[bold red]✖ {res.get('error')}[/bold red]")
                fail_count += 1

        except AuthKeyNotFound:
            console.print("[red]✖ Заблокирован Telegram (AuthKeyNotFound)[/red]")
            fail_count += 1
        except Exception as e:
            err_str = str(e)
            if "invalid Peer" in err_str or "frozen" in err_str.lower():
                console.print("[red]✖ Заморожен в Telegram (frozen)[/red]")
            else:
                console.print(f"[yellow]⚠️ Ошибка ({e})[/yellow]")
            fail_count += 1
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

        # Save progress every 5 accounts
        if idx % 5 == 0:
            with open(DATABASE_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, indent=4)

        await asyncio.sleep(1.5)

    with open(DATABASE_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

    console.print("\n[bold cyan]══════════════════════════════════════════════════════════════════[/bold cyan]")
    console.print(f"[bold green]🎉 ЗАВЕРШЕНО! Успешно восстановлено: {success_count} | Ошибок: {fail_count}[/bold green]")
    console.print("[bold cyan]══════════════════════════════════════════════════════════════════[/bold cyan]\n")

if __name__ == "__main__":
    asyncio.run(main())
