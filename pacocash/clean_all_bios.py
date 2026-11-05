import asyncio
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest

from core.session_manager import load_accounts_db, SESSIONS_DIR
from core.proxy_helper import get_working_proxy_for_account, mark_proxy_dead

console = Console()
CONFIG_FILE = "config.json"
DATABASE_FILE = "database.json"

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def load_database() -> dict:
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

async def clean_account_bio(session_filename: str, cfg: dict, accounts_db: dict, sem: asyncio.Semaphore) -> tuple:
    acc_name = os.path.splitext(session_filename)[0]
    s_path = os.path.join(SESSIONS_DIR, session_filename)
    if not os.path.exists(s_path):
        return acc_name, False, "Сессия не найдена"

    meta = accounts_db.get(acc_name, {})
    dev = meta.get("device", {
        "device_model": "Desktop", "system_version": "Windows 11 x64",
        "app_version": "4.16.8 x64", "system_lang_code": "ru-RU", "lang_code": "ru"
    })

    async with sem:
        client = None
        for attempt in range(2):
            working_proxy = get_working_proxy_for_account(acc_name, meta, force_rotate=(attempt > 0))
            tel_proxy = working_proxy.get("telethon") if isinstance(working_proxy, dict) else None

            client = TelegramClient(
                s_path[:-8],
                cfg["api_id"],
                cfg["api_hash"],
                proxy=tel_proxy,
                device_model=dev.get("device_model", "Desktop"),
                system_version=dev.get("system_version", "Windows 11 x64"),
                app_version=dev.get("app_version", "4.16.8 x64"),
                connection_retries=1,
                retry_delay=1,
                timeout=7.0,
                auto_reconnect=False
            )

            try:
                await asyncio.wait_for(client.connect(), timeout=8.0)
                if not await client.is_user_authorized():
                    await client.disconnect()
                    return acc_name, False, "UNAUTHORIZED (сессия не активна)"

                # Check bio
                me = await client.get_entity('me')
                full = await client(GetFullUserRequest(me))
                old_bio = full.full_user.about or ""

                if old_bio:
                    await client(UpdateProfileRequest(about=""))
                    await client.disconnect()
                    return acc_name, True, f"Очищено (было: '{old_bio[:25]}...')"
                else:
                    await client.disconnect()
                    return acc_name, True, "Уже пусто"

            except Exception as e:
                err_str = str(e)
                try:
                    await client.disconnect()
                except Exception:
                    pass

                is_proxy_err = any(s in err_str.lower() for s in ["407", "proxy", "timeout", "timed out", "connection reset", "socks"])
                if is_proxy_err and attempt == 0:
                    raw_p = working_proxy.get("raw") if isinstance(working_proxy, dict) else None
                    if raw_p:
                        mark_proxy_dead(raw_p)
                    continue

                return acc_name, False, err_str

        return acc_name, False, "Ошибка подключения"

async def main():
    console.print("\n[bold cyan]🧹 ЗАПУСК ТОТАЛЬНОЙ ОЧИСТКИ БИО ДЛЯ ВСЕХ АККАУНТОВ[/bold cyan]")
    cfg = load_config()
    accounts_db = load_accounts_db()

    # Find all session files
    session_files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
    console.print(f"Всего сессий к проверке и очистке: [bold green]{len(session_files)}[/bold green]\n")

    sem = asyncio.Semaphore(5)  # 5 concurrent workers
    success_cnt = 0
    empty_cnt = 0
    fail_cnt = 0

    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(bar_width=35, complete_style="bold green"),
        TextColumn("[bold yellow]{task.completed}/{task.total}[/bold yellow]"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Очистка био...", total=len(session_files))

        tasks = [clean_account_bio(f, cfg, accounts_db, sem) for f in session_files]
        for coro in asyncio.as_completed(tasks):
            acc_name, ok, msg = await coro
            progress.advance(task, 1)
            compact_name = acc_name[:28]
            if ok:
                if "Очищено" in msg:
                    success_cnt += 1
                    console.print(f"  [green]✔ {compact_name}:[/green] [bold yellow]{msg}[/bold yellow]")
                else:
                    empty_cnt += 1
                    console.print(f"  [dim green]✔ {compact_name}: {msg}[/dim green]")
            else:
                fail_cnt += 1
                console.print(f"  [dim red]✖ {compact_name}: {msg[:45]}[/dim red]")

    console.print("\n[bold green]================ ИТОГИ ОЧИСТКИ БИО ================ [/bold green]")
    console.print(f"✔ Успешно удалено био (@winpaco): [bold green]{success_cnt}[/bold green]")
    console.print(f"✔ Уже было пустое био:            [bold cyan]{empty_cnt}[/bold cyan]")
    console.print(f"✖ Пропущено (оффлайн/неактивны):   [bold yellow]{fail_cnt}[/bold yellow]")
    console.print("[bold green]==================================================== [/bold green]\n")

if __name__ == "__main__":
    asyncio.run(main())
