import asyncio
import os
import sys
import json
import random
import time
from datetime import datetime, timedelta

# Fix Windows console utf-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.text import Text
from telethon import TelegramClient

from core.session_manager import sync_sessions, load_accounts_db, SESSIONS_DIR
from core.paco_worker import process_paco_account
from core.referral_manager import get_referral_for_new_account, record_referral_success
from core.wallet_generator import get_or_create_wallet_for_account, load_wallets
from core.paco_withdraw import attempt_account_withdrawal
from core.proxy_helper import get_working_proxy_for_account
from core.balance_syncer import fetch_live_bot_balance

console = Console()
CONFIG_FILE = "config.json"
DATABASE_FILE = "database.json"

def load_config() -> dict:
    default_config = {
        "api_id": 32293468,
        "api_hash": "0897266f179723de0640905e2f7860f3",
        "referral_code": "riJVfpUUR",
        "referral_url": "https://t.me/PacoCashBot?start=riJVfpUUR",
        "referral_mode": "pyramid",
        "root_target_referrals": 4,
        "max_referrals_per_account": 2,
        "bot_username": "PacoCashBot",
        "delay_min": 20,
        "delay_max": 45,
        "batch_size": 5,
        "batch_pause_sec": 120,
        "bio_text": "@winpaco — free case every day!",
        "channels": [
            "BITVA_EKSTRASENS0V",
            "pacocartel",
            "WinPacoLive",
            "w1paco",
            "inona4ka"
        ]
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                default_config.update(json.load(f))
        except Exception:
            pass
    return default_config

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)

def load_database() -> dict:
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_database(db: dict):
    with open(DATABASE_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

def get_hold_status_and_time(d: dict, db: dict, now: datetime):
    if d.get("archived") or d.get("withdrawn") or d.get("status") in ("ARCHIVED", "WITHDRAWN"):
        return "[dim]✔ Выплачено[/dim]", None, False

    status = d.get("status")
    if status != "COMPLETED":
        return "[dim]-[/dim]", None, False
    
    held = float(d.get("held", 0.0))
    avail = float(d.get("available", 0.0))
    pending_ref = float(d.get("pending_ref", 0.0))
    
    # 1. If available >= 1.00, it can be withdrawn right now!
    if avail >= 1.0:
        return f"[bold green]✅ Готов (${avail:.2f})[/bold green]", 0, True

    # 2. Check hold timers only if there is money actually in hold!
    active_hu = None

    # Referral hold (when invited children reach 48h)
    if pending_ref > 0:
        children = d.get("children", [])
        child_hu_list = []
        for ch_name in children:
            ch_data = db.get(ch_name, {})
            ch_hu = ch_data.get("hold_until")
            if ch_hu:
                try:
                    child_hu_list.append(datetime.fromisoformat(ch_hu))
                except Exception:
                    pass
            elif ch_data.get("completed_at"):
                try:
                    child_hu_list.append(datetime.fromisoformat(ch_data.get("completed_at")) + timedelta(days=2))
                except Exception:
                    pass
        if child_hu_list:
            active_hu = max(child_hu_list)
    
    # Task hold (when own tasks reach 48h)
    if held > 0:
        hu_str = d.get("hold_until")
        task_hu = None
        if hu_str:
            try:
                task_hu = datetime.fromisoformat(hu_str)
            except Exception:
                pass
        elif d.get("completed_at"):
            try:
                task_hu = datetime.fromisoformat(d.get("completed_at")) + timedelta(days=2)
            except Exception:
                pass
        if task_hu:
            if active_hu is None or task_hu > active_hu:
                active_hu = task_hu

    # If there is an active hold period
    if active_hu and active_hu > now:
        diff = active_hu - now
        sec = int(diff.total_seconds())
        hrs = sec // 3600
        mins = (sec % 3600) // 60
        if hrs > 0:
            return f"[bold yellow]⏳ {hrs}ч {mins:02d}м[/bold yellow]", sec, False
        else:
            return f"[bold orange3]⏳ {mins}м[/bold orange3]", sec, False

    # No active hold:
    if avail > 0:
        return f"[dim yellow]⚪ Ждет реф. (${avail:.2f})[/dim yellow]", None, False
    else:
        return "[dim]- ($0)[/dim]", None, False

def render_banner():
    os.system('cls' if os.name == 'nt' else 'clear')
    banner = Text()
    banner.append(" 💰 ", style="bold yellow")
    banner.append("PACOCASH SMART FARM v2.2", style="bold green cyan")
    banner.append(" | ", style="dim white")
    banner.append("REAL-TIME HOLD TIMERS & CRYPTOBOT", style="bold yellow")
    
    # Calculate live hold stats for instant visibility
    db = load_database()
    now = datetime.now()
    unlocked = 0
    in_hold = 0
    archived = 0
    min_hold_sec = None
    for d in db.values():
        if d.get("archived") or d.get("status") == "ARCHIVED":
            archived += 1
            continue
        if d.get("status") == "COMPLETED":
            _, rem_sec, is_ready = get_hold_status_and_time(d, db, now)
            if is_ready:
                unlocked += 1
            else:
                in_hold += 1
                if rem_sec is not None and (min_hold_sec is None or rem_sec < min_hold_sec):
                    min_hold_sec = rem_sec

    arch_str = f" | [dim cyan]📦 {archived} в архиве[/dim cyan]" if archived > 0 else ""
    if min_hold_sec is not None:
        rem_h = min_hold_sec // 3600
        rem_m = (min_hold_sec % 3600) // 60
        unlock_dt = now + timedelta(seconds=min_hold_sec)
        hold_subtitle = f"⏳ [bold green]{unlocked} готово к выводу[/bold green] | [yellow]{in_hold} в холде[/yellow] | Ближайший вывод через: [bold yellow]{rem_h}ч {rem_m:02d}м[/bold yellow] ({unlock_dt.strftime('%H:%M')}){arch_str}"
    elif unlocked > 0:
        hold_subtitle = f"🎉 [bold green]Все {unlocked} аккаунтов разблокированы и готовы к выводу![/bold green]{arch_str}"
    else:
        hold_subtitle = f"[dim cyan]Честный учет балансов и таймеров холда | Выплаты в CryptoBot{arch_str}[/dim cyan]"

    console.print(Panel(
        banner,
        subtitle=hold_subtitle,
        border_style="green",
        expand=False
    ))

async def countdown_pause(seconds: int, label: str):
    with Progress(
        SpinnerColumn("clock"),
        TextColumn("[bold cyan]⏳ {task.fields[label]}: [/bold cyan]"),
        BarColumn(bar_width=30, complete_style="bold green", finished_style="dim green"),
        TextColumn("[bold yellow]{task.completed}/{task.total} сек[/bold yellow]"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("pause", total=seconds, label=label)
        for _ in range(seconds):
            await asyncio.sleep(1)
            progress.advance(task, 1)

async def run_farm_mode():
    render_banner()
    cfg = load_config()
    db = load_database()

    console.print("[bold cyan]🔄 Синхронизация сессий...[/bold cyan]")
    accounts = sync_sessions()
    if not accounts:
        console.print("[bold red][!] Сессии не найдены в TG_farm или RB_Autimatic.[/bold red]")
        Prompt.ask("\nНажмите Enter для возврата в меню")
        return

    # Filter pending accounts
    pending = []
    for acc_name, s_path, meta in accounts:
        record = db.get(acc_name, {})
        if record.get("status") == "COMPLETED" or record.get("withdrawn") or record.get("archived"):
            continue
        pending.append((acc_name, s_path, meta))

    console.print(f"[bold green]✔ Всего готовых аккаунтов в ферме: {len(accounts)}[/bold green]")
    console.print(f"[bold yellow]📋 Осталось обработать: {len(pending)} из {len(accounts)}[/bold yellow]\n")
    
    if not pending:
        console.print("[bold green]🎉 Все аккаунты уже успешно обработаны![/bold green]")
        Prompt.ask("\nНажмите Enter для возврата в меню")
        return

    console.print(Panel(
        "[white]Для защиты от антифрода не рекомендуется регистрировать 70 аккаунтов за 1 час.\n"
        "Оптимально запускать пачками по 5–15 аккаунтов в сессию.[/white]",
        title="[bold yellow]🛡️ ЗАЩИТА ОТ СПАЙКА (ANTI-SPIKE)[/bold yellow]",
        border_style="yellow"
    ))
    max_to_run = IntPrompt.ask(
        f"Сколько аккаунтов обработать сейчас? (1 - {len(pending)})",
        default=min(10, len(pending))
    )
    batch_accounts = pending[:max_to_run]

    api_id = cfg.get("api_id")
    api_hash = cfg.get("api_hash")
    root_code = cfg.get("referral_code", "riJVfpUUR")
    channels = cfg.get("channels", [])
    bio_text = cfg.get("bio_text", "@winpaco — free case every day!")
    d_min = cfg.get("delay_min", 20)
    d_max = cfg.get("delay_max", 45)
    batch_size = cfg.get("batch_size", 5)
    batch_pause = cfg.get("batch_pause_sec", 120)

    success_cnt = 0
    err_cnt = 0

    for idx, (acc_name, s_path, meta) in enumerate(batch_accounts, 1):
        working_proxy = get_working_proxy_for_account(acc_name, meta)
        prx = working_proxy.get("raw", "Прямой IP") if working_proxy else "Прямой IP"
        ip_label = prx.split(":")[0]

        # 1. Determine optimal referral code (Pyramid or Single)
        assigned_ref, ref_label = get_referral_for_new_account(db, cfg)

        # 2. Pre-generate or fetch dedicated TON wallet
        wallet = get_or_create_wallet_for_account(acc_name)

        console.print(f"[bold cyan]───────────────────────────────────────────────────────[/bold cyan]")
        console.print(f"[bold white][{idx}/{len(batch_accounts)}][/bold white] Аккаунт: [bold yellow]{acc_name}[/bold yellow] | IP: [dim]{ip_label}[/dim]")
        console.print(f"  [bold magenta]🌳 Реферер:[/bold magenta] [bold white]{ref_label}[/bold white] (код: [cyan]{assigned_ref}[/cyan])")
        console.print(f"  [bold blue]💎 TON-кошелек:[/bold blue] [cyan]{wallet['address']}[/cyan]")

        res = await process_paco_account(
            account_name=acc_name,
            session_file=s_path,
            api_id=api_id,
            api_hash=api_hash,
            referral_code=assigned_ref,
            channels=channels,
            bio_text=bio_text,
            meta=meta
        )

        now_str = datetime.now().isoformat()
        if res.get("ok"):
            success_cnt += 1
            held = res.get("held_balance", 0.0)
            avail = res.get("available_balance", 0.0)
            pending_bal = res.get("pending_balance", 0.0)
            own_ref = res.get("own_ref_code")
            hold_until = (datetime.now() + timedelta(days=2)).isoformat()

            db[acc_name] = {
                "status": "COMPLETED",
                "phone": res.get("phone"),
                "parent_ref": assigned_ref,
                "own_ref_code": own_ref,
                "ton_address": wallet["address"],
                "held": held,
                "available": avail,
                "pending_ref": pending_bal,
                "referrals_count": 0,
                "children": [],
                "completed_at": now_str,
                "hold_until": hold_until,
                "error": None
            }
            # Record referral relationship in parent account
            record_referral_success(db, assigned_ref, acc_name, root_code)
            save_database(db)

            console.print(f"  [bold green]✔ Задания выполнены![/bold green] Подписок: {res.get('joined_channels')} | Верификация: [green]OK[/green]")
            console.print(f"  [bold green]🔗 Своя рефка получена:[/bold green] [bold cyan]{own_ref or 'Не получена'}[/bold cyan]")
            console.print(f"  [bold green]💰 Баланс:[/bold green] Доступно: [dim]${avail:.2f}[/dim] | В холде (задания 48ч): [bold yellow]${held:.2f}[/bold yellow] | Ожидает (рефы): [bold cyan]${pending_bal:.2f}[/bold cyan]")
        else:
            err_cnt += 1
            err_msg = res.get("error", "Неизвестная ошибка")
            db[acc_name] = {
                "status": "FAILED",
                "completed_at": now_str,
                "error": err_msg
            }
            save_database(db)
            console.print(f"  [bold red]✖ Ошибка:[/bold red] {err_msg}")

        # Anti-Spike pauses
        if idx < len(batch_accounts):
            if idx % batch_size == 0:
                console.print(f"\n[bold yellow]🛡️ Пауза охлаждения пачки ({batch_pause} сек) для естественного темпа...[/bold yellow]")
                await countdown_pause(batch_pause, "Охлаждение пачки")
            else:
                pause_sec = random.randint(d_min, d_max)
                next_name = batch_accounts[idx][0]
                await countdown_pause(pause_sec, f"Пауза перед {next_name}")

    console.print(Panel(
        f"[bold green]Партия успешно завершена![/bold green]\n"
        f"Обработано в этой сессии: [bold green]{success_cnt}[/bold green] | С ошибками: [bold red]{err_cnt}[/bold red]",
        title="[bold yellow]📊 ИТОГИ СЕССИИ[/bold yellow]",
        border_style="green"
    ))
    Prompt.ask("\nНажмите Enter для возврата в меню")


def format_compact_account_name(full_name: str, max_width: int = 32) -> str:
    """Formats verbose account name into a clean, single-line representation fitting max_width."""
    parts = full_name.split()
    geo = parts[0] if parts and parts[0].startswith("[") and parts[0].endswith("]") else ""
    phone = None
    names = []
    for p in (parts[1:] if geo else parts):
        if p.startswith("+") or (p.isdigit() and len(p) >= 10):
            phone = p
        elif p.isdigit() and len(p) == 4 and int(p) in range(2018, 2030):
            continue
        else:
            names.append(p)

    ph_short = f"{phone[:5]}..{phone[-3:]}" if phone and len(phone) > 9 else (phone or "")

    if names:
        first = names[0]
        last_init = f" {names[-1][0]}." if len(names) > 1 else ""
        name_str = f"{first}{last_init}"
    else:
        name_str = ""

    prefix = f"{geo} " if geo else ""
    suffix = f" ({ph_short})" if ph_short else ""

    res = f"{prefix}{name_str}{suffix}".strip()
    if len(res) > max_width:
        res = res[:max_width-1] + "…"
    return res

async def show_database_stats():
    render_banner()
    sync_sessions()
    cfg = load_config()
    db = load_database()
    accounts_db = load_accounts_db()

    w_file = "withdrawals.json"
    w_list = json.load(open(w_file, "r", encoding="utf-8")) if os.path.exists(w_file) else []
    withdrawn_set = set(item.get("account") for item in w_list if isinstance(item, dict) and "account" in item)
    total_withdrawn_usd = sum(float(x.get("amount", 0.0)) for x in w_list)

    # Automatically flag already withdrawn accounts as archived
    for name, d in db.items():
        if name in withdrawn_set:
            d["archived"] = True
            d["withdrawn"] = True

    # Filter candidate active accounts to audit (strictly unarchived and not already withdrawn)
    candidates = [
        (name, d) for name, d in db.items()
        if not d.get("archived") and d.get("status") != "DEAD" and name not in withdrawn_set
    ]

    if not candidates:
        console.print("[bold yellow]База данных пуста либо все аккаунты уже в архиве.[/bold yellow]")
        Prompt.ask("\nНажмите Enter для возврата в меню")
        return

    console.print(Panel(
        f"[white]Прямой параллельный опрос PacoCashBot через живые прокси.\n"
        f"Слетевшие сессии и отработавшие аккаунты ($0) автоматически удаляются из таблицы.[/white]\n\n"
        f"Активных аккаунтов к проверке: [bold cyan]{len(candidates)}[/bold cyan]",
        title="[bold yellow]⚡ ЖИВОЙ АУДИТ ФЕРМЫ: ОПРОС БАЛАНСОВ И АВТО-ОЧИСТКА[/bold yellow]",
        border_style="yellow"
    ))

    sem = asyncio.Semaphore(6)
    dead_count = 0
    retired_count = 0
    net_err_count = 0
    ready_to_withdraw = []

    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(bar_width=30, complete_style="bold green"),
        TextColumn("[bold yellow]{task.completed}/{task.total}[/bold yellow]"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task_id = progress.add_task("Опрос балансов и очистка...", total=len(candidates))

        async def audit_one(name, d):
            nonlocal dead_count, retired_count, net_err_count
            s_path = os.path.join(SESSIONS_DIR, f"{name}.session")
            if not os.path.exists(s_path):
                d["status"] = "DEAD"
                d["archived"] = True
                d["error"] = "Сессия отсутствует на диске"
                dead_count += 1
                progress.advance(task_id, 1)
                return

            meta = accounts_db.get(name, {})
            async with sem:
                try:
                    res = await fetch_live_bot_balance(name, s_path, cfg["api_id"], cfg["api_hash"], meta)
                    if res.get("is_dead"):
                        d["status"] = "DEAD"
                        d["archived"] = True
                        d["error"] = res.get("error", "Слетела сессия")
                        dead_count += 1
                        try:
                            os.makedirs(ARCHIVE_DIR, exist_ok=True)
                            dst = os.path.join(ARCHIVE_DIR, f"{name}.session")
                            if not os.path.exists(dst):
                                shutil.move(s_path, dst)
                            else:
                                os.remove(s_path)
                        except Exception:
                            pass
                    elif res.get("ok"):
                        avail = res.get("available", 0.0)
                        held = res.get("held", 0.0)
                        pending = res.get("pending", 0.0)
                        d["available"] = avail
                        d["held"] = held
                        d["pending_ref"] = pending

                        if avail == 0.0 and held == 0.0 and pending == 0.0:
                            if name in withdrawn_set or d.get("withdrawn"):
                                d["status"] = "ARCHIVED"
                                d["archived"] = True
                                d["withdrawn"] = True
                                retired_count += 1
                                try:
                                    os.makedirs(ARCHIVE_DIR, exist_ok=True)
                                    dst = os.path.join(ARCHIVE_DIR, f"{name}.session")
                                    if not os.path.exists(dst):
                                        shutil.move(s_path, dst)
                                    else:
                                        os.remove(s_path)
                                except Exception:
                                    pass
                        elif avail >= 1.00:
                            ready_to_withdraw.append((name, avail))
                    else:
                        net_err_count += 1
                except Exception:
                    net_err_count += 1
                finally:
                    progress.advance(task_id, 1)

        tasks = [audit_one(name, d) for name, d in candidates]
        await asyncio.gather(*tasks)

    save_database(db)

    # Filter active accounts with non-zero balances
    now = datetime.now()
    table = Table(title="📊 Статистика активных аккаунтов PacoCash (Живые данные)", border_style="cyan")
    table.add_column("№", style="dim", width=4)
    table.add_column("Аккаунт", style="cyan", no_wrap=True, width=32)
    table.add_column("Рефы", justify="center", width=6)
    table.add_column("Доступно", justify="right", width=10)
    table.add_column("В холде", justify="right", width=10)
    table.add_column("Итого", justify="right", style="bold yellow", width=9)
    table.add_column("Статус / Таймер", justify="center", width=24)

    total_avail = 0.0
    total_held = 0.0
    total_pending = 0.0
    unlocked_cnt = 0
    in_hold_cnt = 0
    waiting_refs_cnt = 0
    archived_cnt = 0
    active_hold_seconds = []

    row_idx = 1
    for name, d in db.items():
        status = d.get("status", "UNKNOWN")
        is_retired = d.get("archived") or d.get("withdrawn") or status in ("ARCHIVED", "WITHDRAWN", "DEAD")
        if is_retired:
            archived_cnt += 1
            continue

        avail = float(d.get("available", 0.0))
        held = float(d.get("held", 0.0))
        pending_ref = float(d.get("pending_ref", 0.0))
        total_in_hold = held + pending_ref
        total_acc = avail + total_in_hold

        # Only hide accounts that are explicitly retired/archived with 0 balance
        if total_acc == 0 and is_retired:
            continue

        st_color = "green" if status == "COMPLETED" else "white"
        total_avail += avail
        total_held += held
        total_pending += pending_ref

        hold_str, rem_sec, is_ready = get_hold_status_and_time(d, db, now)
        if avail >= 1.00:
            unlocked_cnt += 1
            hold_str = f"[bold green]✅ Готов (${avail:.2f})[/bold green]"
        elif rem_sec is not None and rem_sec > 0:
            in_hold_cnt += 1
            active_hold_seconds.append(rem_sec)
        else:
            waiting_refs_cnt += 1

        avail_styled = f"[bold green]${avail:.2f}[/bold green]" if avail > 0 else f"[dim]${avail:.2f}[/dim]"
        hold_styled = f"[bold yellow]${total_in_hold:.2f}[/bold yellow]" if total_in_hold > 0 else f"[dim]${total_in_hold:.2f}[/dim]"
        refs_count = d.get("referrals_count", len(d.get("children", [])))
        compact_name = format_compact_account_name(name)

        table.add_row(
            str(row_idx),
            f"[{st_color}]{compact_name}[/{st_color}]",
            str(refs_count),
            avail_styled,
            hold_styled,
            f"${total_acc:.2f}",
            hold_str
        )
        row_idx += 1

    console.print(table)

    timeline_text = ""
    if active_hold_seconds:
        min_sec = min(active_hold_seconds)
        max_sec = max(active_hold_seconds)
        earliest_dt = now + timedelta(seconds=min_sec)
        latest_dt = now + timedelta(seconds=max_sec)
        earliest_str = f"{min_sec // 3600}ч {(min_sec % 3600) // 60:02d}м ({earliest_dt.strftime('%d.%m в %H:%M')})"
        latest_str = f"{max_sec // 3600}ч {(max_sec % 3600) // 60:02d}м ({latest_dt.strftime('%d.%m в %H:%M')})"
        timeline_text = (
            f"\n⏰ [bold white]Ближайшая разблокировка холда:[/bold white]  [bold yellow]{earliest_str}[/bold yellow]\n"
            f"🏁 [bold white]Разблокировка всей фермы:[/bold white]        [bold yellow]{latest_str}[/bold yellow]"
        )

    dead_note = f" | [red]💀 Слетело: {dead_count}[/red]" if dead_count > 0 else ""
    cleaned_note = f" | [dim cyan]📦 Очищено отработавших: {retired_count}[/dim cyan]" if retired_count > 0 else ""

    console.print(Panel(
        f"[bold white]Активных в работе:[/bold white] [bold cyan]{row_idx - 1}[/bold cyan] | "
        f"[bold white]В холде (ждут таймер):[/bold white] [bold yellow]{in_hold_cnt}[/bold yellow] | "
        f"[bold white]Ждут рефералов ($0.50):[/bold white] [bold white]{waiting_refs_cnt}[/bold white] | "
        f"[bold white]Готовы к выводу ($1+):[/bold white] [bold green]{unlocked_cnt}[/bold green]"
        f"{dead_note}{cleaned_note}\n\n"
        f"🟢 [bold white]Доступно к выводу прямо сейчас:[/bold white] [bold green]${total_avail:.2f}[/bold green]\n"
        f"⏳ [bold white]В холде за задания (48ч):[/bold white]       [bold yellow]${total_held:.2f}[/bold yellow]\n"
        f"🕵️ [bold white]Ожидает проверки за рефералов (48ч):[/bold white] [bold cyan]${total_pending:.2f}[/bold cyan]\n"
        f"💰 [bold white]ОБЩИЙ ЖИВОЙ БАЛАНС ФЕРМЫ (ПОТЕНЦИАЛ):[/bold white] [bold yellow]${total_avail + total_held + total_pending:.2f}[/bold yellow]\n"
        f"📦 [dim cyan]Выведено чеками в архив:[/dim cyan]               [dim cyan]{len(w_list)} чеков на ${total_withdrawn_usd:.2f} USDT[/dim cyan]"
        f"{timeline_text}",
        title="[bold green]💰 ЧЕСТНЫЙ ЖИВОЙ БАЛАНС И ТАЙМЕРЫ ХОЛДА[/bold green]",
        border_style="green"
    ))

    if unlocked_cnt > 0:
        ch = Prompt.ask("\n[bold magenta]5[/bold magenta] - 💸 Вывести готовые средства в CryptoBot | [bold white]Enter[/bold white] - Назад в меню", default="")
        if ch == "5":
            await run_withdrawal_mode()
    else:
        Prompt.ask("\nНажмите Enter для возврата в меню")

def show_referral_tree():
    render_banner()
    db = load_database()

    if not db:
        console.print("[bold yellow]База пуста.[/bold yellow]")
        Prompt.ask("\nНажмите Enter для возврата в меню")
        return

    table = Table(title="🌳 Реферальное дерево PacoCash", border_style="green")
    table.add_column("№", style="dim", width=3, justify="right")
    table.add_column("Аккаунт", style="cyan", no_wrap=True, width=28)
    table.add_column("Реф-код", style="bold cyan", width=10, no_wrap=True)
    table.add_column("От кого", style="dim", width=10, no_wrap=True)
    table.add_column("Рефы", justify="center", width=8)
    table.add_column("Баланс", justify="right", width=8)
    table.add_column("Статус", justify="center", width=12)

    idx = 1
    for acc_name, d in db.items():
        if d.get("status") in ("DELETED", "DEAD") or d.get("archived") and d.get("status") == "DELETED":
            continue

        children = d.get("children", [])
        ch_str = f"🌿 {len(children)}" if children else "[dim]0[/dim]"
        avail = float(d.get("available") or 0.0)
        held = float(d.get("held") or 0.0)
        pending = float(d.get("pending_ref") or 0.0)
        tot = avail + held + pending

        if d.get("archived") or d.get("withdrawn"):
            status_str = "[dim cyan]📦 Архив[/dim cyan]"
        elif tot >= 1.0:
            status_str = "[bold green]✅ Готов[/bold green]"
        elif tot > 0:
            status_str = "[yellow]⏳ Холд[/yellow]"
        else:
            status_str = "[dim]-[/dim]"

        compact_name = format_compact_account_name(acc_name)
        table.add_row(
            str(idx),
            compact_name,
            str(d.get("own_ref_code", "-")),
            str(d.get("parent_ref", "-")),
            ch_str,
            f"${tot:.2f}",
            status_str
        )
        idx += 1

    console.print(table)
    Prompt.ask("\nНажмите Enter для возврата в меню")

async def run_withdrawal_mode():
    render_banner()
    cfg = load_config()
    db = load_database()
    accounts_db = load_accounts_db()

    receiver_name = cfg.get("receiver_account", "[RU] Xxxcalibur +79936124946 2025")

    console.print(Panel(
        f"[white]Скрипт проверяет реальный баланс в боте и выводит средства ТОЛЬКО с тех аккаунтов,\n"
        f"где уже доступно >= $1.00 (без пустых попыток и фрода).\n"
        f"Чеки автоматически зачисляются на {receiver_name}.[/white]",
        title="[bold yellow]💸 АВТОМАТИЧЕСКИЙ ВЫВОД СРЕДСТВ В CRYPTOBOT[/bold yellow]",
        border_style="yellow"
    ))

    now = datetime.now()
    # Find active candidates that could potentially have >= $1.00 or hold expired
    candidates = []
    for name, d in db.items():
        if d.get("archived") or d.get("withdrawn") or d.get("status") == "DEAD":
            continue
        avail = float(d.get("available") or 0.0)
        held = float(d.get("held") or 0.0)
        _, rem_sec, is_ready = get_hold_status_and_time(d, db, now)
        if avail >= 1.00 or is_ready or (held > 0 and (rem_sec is None or rem_sec <= 0)):
            candidates.append((name, d))

    if not candidates:
        active_secs = []
        for a_name, a_d in db.items():
            if not a_d.get("archived") and not a_d.get("withdrawn"):
                _, rem, is_rdy = get_hold_status_and_time(a_d, db, now)
                if not is_rdy and rem is not None and rem > 0:
                    active_secs.append(rem)

        time_msg = ""
        if active_secs:
            min_s = min(active_secs)
            earliest_dt = now + timedelta(seconds=min_s)
            time_msg = f"\n\n⏰ [bold white]Ближайшая разблокировка холда:[/bold white] через [bold yellow]{min_s // 3600}ч {(min_s % 3600) // 60:02d}м[/bold yellow] (в [bold cyan]{earliest_dt.strftime('%d.%m в %H:%M')}[/bold cyan])"

        console.print(Panel(
            f"[bold yellow]❌ На данный момент нет доступных к выводу средств (минимум $1.00).[/bold yellow]\n\n"
            f"[white]Все средства активной фермы сейчас удерживаются ботом на 48-часовой проверке.\n"
            f"Как только таймер истечет, бот разблокирует выплату.[/white]"
            f"{time_msg}",
            title="[bold yellow]⏳ ВСЕ СРЕДСТВА В ХОЛДЕ[/bold yellow]",
            border_style="yellow"
        ))
        Prompt.ask("\nНажмите Enter для возврата в меню")
        return

    console.print(f"[bold cyan]🔍 Экспресс-проверка кандидатов ({len(candidates)} акк.) в PacoCashBot...[/bold cyan]")
    sem = asyncio.Semaphore(5)
    eligible = []

    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(bar_width=30, complete_style="bold green"),
        TextColumn("[bold yellow]{task.completed}/{task.total}[/bold yellow]"),
        console=console,
        transient=True
    ) as progress:
        task_id = progress.add_task("Проверка доступного баланса...", total=len(candidates))

        async def verify_one(name, d):
            s_path = os.path.join(SESSIONS_DIR, f"{name}.session")
            if not os.path.exists(s_path):
                progress.advance(task_id, 1)
                return

            meta = accounts_db.get(name, {})
            async with sem:
                try:
                    res = await fetch_live_bot_balance(name, s_path, cfg["api_id"], cfg["api_hash"], meta)
                    if res.get("is_dead"):
                        d["status"] = "DEAD"
                        d["archived"] = True
                    elif res.get("ok"):
                        avail = res.get("available", 0.0)
                        d["available"] = avail
                        d["held"] = res.get("held", 0.0)
                        d["pending_ref"] = res.get("pending", 0.0)
                        if avail >= 1.00:
                            eligible.append((name, d, avail))
                except Exception:
                    pass
                finally:
                    progress.advance(task_id, 1)

        tasks = [verify_one(name, d) for name, d in candidates]
        await asyncio.gather(*tasks)

    save_database(db)

    # IF NO ELIGIBLE ACCOUNTS FOUND LIVE:
    if not eligible:
        now = datetime.now()
        active_secs = []
        for a_name, a_d in db.items():
            if not a_d.get("archived") and not a_d.get("withdrawn"):
                _, rem, is_rdy = get_hold_status_and_time(a_d, db, now)
                if not is_rdy and rem is not None and rem > 0:
                    active_secs.append(rem)

        time_msg = ""
        if active_secs:
            min_s = min(active_secs)
            earliest_dt = now + timedelta(seconds=min_s)
            time_msg = f"\n\n⏰ [bold white]Ближайшая разблокировка холда:[/bold white] через [bold yellow]{min_s // 3600}ч {(min_s % 3600) // 60:02d}м[/bold yellow] (в [bold cyan]{earliest_dt.strftime('%d.%m в %H:%M')}[/bold cyan])"

        console.print(Panel(
            f"[bold yellow]❌ На данный момент нет аккаунтов с доступным балансом >= $1.00.[/bold yellow]\n\n"
            f"[white]Все проверенные аккаунты сейчас находятся в холде либо имеют баланс < $1.00.\n"
            f"Пустые попытки вывода отменены для защиты от антифрода бота.[/white]"
            f"{time_msg}",
            title="[bold yellow]⏳ СРЕДСТВА В ХОЛДЕ (ВЫВОД ПОКА НЕ ДОСТУПЕН)[/bold yellow]",
            border_style="yellow"
        ))
        Prompt.ask("\nНажмите Enter для возврата в меню")
        return

    # IF ELIGIBLE ACCOUNTS FOUND:
    total_to_withdraw = sum(item[2] for item in eligible)
    table = Table(title=f"💸 Аккаунты, готовые к выводу прямо сейчас ({len(eligible)} шт.)", border_style="green")
    table.add_column("№", style="dim", width=3, justify="right")
    table.add_column("Аккаунт", style="cyan", no_wrap=True, width=30)
    table.add_column("К выводу", justify="right", style="bold green", width=12)
    table.add_column("Кошелек-получатель (CryptoBot)", style="bold cyan")

    for i, (name, d, amt) in enumerate(eligible, 1):
        table.add_row(
            str(i),
            format_compact_account_name(name),
            f"${amt:.2f}",
            receiver_name
        )

    console.print(table)
    console.print(f"\n[bold green]Общая сумма к зачислению:[/bold green] [bold yellow]${total_to_withdraw:.2f} USDT[/bold yellow]\n")

    if not Confirm.ask(f"Запустить вывод для {len(eligible)} аккаунтов на {receiver_name}?", default=True):
        return

    for idx, (acc_name, d, amt) in enumerate(eligible, 1):
        s_path = os.path.join(SESSIONS_DIR, f"{acc_name}.session")
        if not os.path.exists(s_path):
            console.print(f"[red]Сессия не найдена: {acc_name}[/red]")
            continue

        meta = accounts_db.get(acc_name, {})
        dev = meta.get("device", {
            "device_model": "Desktop", "system_version": "Windows 11 x64",
            "app_version": "4.16.8 x64", "system_lang_code": "ru-RU", "lang_code": "ru"
        })

        client = None
        connected = False
        working_proxy = None
        for attempt in range(2):
            working_proxy = get_working_proxy_for_account(acc_name, meta, force_rotate=(attempt > 0))
            tel_proxy = working_proxy.get("telethon") if isinstance(working_proxy, dict) else None
            prx_ip = working_proxy.get("ip", "direct") if isinstance(working_proxy, dict) else "direct"

            if attempt == 0:
                console.print(f"\n[cyan][{idx}/{len(eligible)}][/cyan] Вывод для [yellow]{acc_name}[/yellow] (Proxy: [dim]{prx_ip}[/dim])...")
            else:
                console.print(f"  [yellow]🔄 Смена прокси на свежий из RB_Autimatic: [dim]{prx_ip}[/dim]...[/yellow]")

            client = TelegramClient(
                s_path, cfg["api_id"], cfg["api_hash"],
                proxy=tel_proxy,
                device_model=dev.get("device_model", "Desktop"),
                system_version=dev.get("system_version", "Windows 11 x64"),
                app_version=dev.get("app_version", "4.16.8 x64"),
                connection_retries=1,
                retry_delay=1
            )
            try:
                await asyncio.wait_for(client.connect(), timeout=9.0)
                connected = True
                break
            except Exception as conn_err:
                err_str = str(conn_err)
                is_proxy_err = any(s in err_str.lower() for s in ["407", "proxy", "timeout", "timed out", "connection reset", "socks", "tunnel connection failed"])
                if is_proxy_err and attempt == 0:
                    raw_p = working_proxy.get("raw") if isinstance(working_proxy, dict) else None
                    if raw_p:
                        from core.proxy_helper import mark_proxy_dead
                        mark_proxy_dead(raw_p)
                    continue
                console.print(f"  [red]Ошибка подключения ({acc_name}): {conn_err}[/red]")
                break

        if not connected or not client:
            continue

        try:
            res = await attempt_account_withdrawal(client, acc_name, meta=meta, amount=amt)

            # Disconnect withdrawing client BEFORE claiming cheque to prevent SQLite database lock on receiver
            try:
                await client.disconnect()
            except Exception:
                pass
            if res.get("ok"):
                check_url = res.get("check_url")
                if check_url:
                    console.print(f"  [bold green]🎉 ВЫПЛАТА ПОЛУЧЕНА![/bold green] Чек: [bold cyan]{check_url}[/bold cyan]")
                    d["check_url"] = check_url

                    # Auto-claim check directly to receiver account (e.g. Xxxcalibur)
                    claimed_by = None
                    if cfg.get("auto_claim_cryptobot", True):
                        console.print(f"  [cyan]📥 Активация чека на профиль [bold yellow]{receiver_name}[/bold yellow]...[/cyan]")
                        try:
                            from core.cryptobot_claimer import claim_check_with_account
                            claim_res = await claim_check_with_account(check_url, receiver_account=receiver_name, cfg=cfg)
                            if claim_res.get("ok"):
                                rep_msg = claim_res.get("message", "").splitlines()[0] if claim_res.get("message") else "Успешно"
                                console.print(f"  [bold green]✔ USDT зачислены в CryptoBot на {receiver_name}![/bold green] ({rep_msg})")
                                claimed_by = receiver_name
                            else:
                                console.print(f"  [yellow]⚠️ Не удалось активировать автоматически: {claim_res.get('error')}[/yellow]")
                        except Exception as claim_err:
                            console.print(f"  [yellow]⚠️ Ошибка авто-активации: {claim_err}[/yellow]")

                    # Append to withdrawals.json
                    try:
                        w_file = "withdrawals.json"
                        w_list = json.load(open(w_file, "r", encoding="utf-8")) if os.path.exists(w_file) else []
                        w_list.append({
                            "account": acc_name,
                            "amount": amt,
                            "check_url": check_url,
                            "claimed_by": claimed_by,
                            "timestamp": datetime.now().isoformat()
                        })
                        with open(w_file, "w", encoding="utf-8") as f:
                            json.dump(w_list, f, ensure_ascii=False, indent=4)
                    except Exception:
                        pass
                else:
                    console.print(f"  [bold green]✔ Запрос на вывод отправлен![/bold green] Ответ: {res.get('message')}")
                d["withdrawn"] = True
                d["withdrawn_at"] = datetime.now().isoformat()
                d["available"] = 0.0
                save_database(db)

                # Auto-retire fully-squeezed account: wipe bio and move session to archived_sessions/
                try:
                    from core.lifecycle_manager import retire_account
                    ret_res = await retire_account(acc_name, cfg, db)
                    if ret_res.get("ok"):
                        console.print(f"  [bold green]📦 Аккаунт дожат:[/bold green] био очищено, сессия перенесена в archived_sessions/")

                    # If this account was a parent, retire its leaf children as well
                    for ch_name in d.get("children", []):
                        ch_data = db.get(ch_name, {})
                        if not ch_data.get("children"):
                            ch_ret = await retire_account(ch_name, cfg, db)
                            if ch_ret.get("ok"):
                                console.print(f"  [bold green]📦 Реферал {ch_name} дожат:[/bold green] био очищено, сессия перенесена в архив")
                    save_database(db)
                except Exception as ret_err:
                    console.print(f"  [dim yellow]Архивация: {ret_err}[/dim yellow]")
            else:
                err_msg = res.get('error', '')
                if "Недостаточно" in err_msg or res.get("status") == "INSUFFICIENT_FUNDS":
                    console.print(f"  [bold yellow]⏳ Холд активен в боте:[/bold yellow] {err_msg}")
                    d["available"] = 0.0
                    save_database(db)
                else:
                    console.print(f"  [bold red]✖ Не удалось вывести:[/bold red] {err_msg}")
        except Exception as conn_err:
            console.print(f"  [bold red]✖ Ошибка подключения:[/bold red] {conn_err}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

        await asyncio.sleep(3)

    Prompt.ask("\nНажмите Enter для возврата в меню")

def settings_menu():
    render_banner()
    cfg = load_config()

    console.print("[bold cyan]⚙️ Текущие настройки фермы:[/bold cyan]\n")
    console.print(f"1. Режим рефералов:       [bold yellow]{cfg.get('referral_mode', 'pyramid').upper()}[/bold yellow] (пирамида / одиночный)")
    console.print(f"2. Рефка основы:           [bold yellow]{cfg.get('referral_code')}[/bold yellow]")
    console.print(f"3. Рефов на основу:        [bold yellow]{cfg.get('root_target_referrals', 4)} шт.[/bold yellow]")
    console.print(f"4. Рефов на каждый аккаунт:[bold yellow]{cfg.get('max_referrals_per_account', 2)} шт.[/bold yellow] (для разблокировки вывода $1.00)")
    console.print(f"5. Размер партии (пачки):  [bold yellow]{cfg.get('batch_size', 5)} аккаунтов[/bold yellow]")
    console.print(f"6. Задержки между акками:  [bold yellow]{cfg.get('delay_min')} - {cfg.get('delay_max')} сек[/bold yellow]")
    console.print(f"7. Охлаждение пачки:       [bold yellow]{cfg.get('batch_pause_sec', 120)} сек[/bold yellow]\n")

    ch = Prompt.ask("Что изменить? (1-Режим рефералов, 2-Рефка основы, 4-Рефов на аккаунт, enter-назад)", default="")
    if ch == "1":
        new_mode = Prompt.ask("Выберите режим", choices=["pyramid", "single"], default="pyramid")
        cfg["referral_mode"] = new_mode
        save_config(cfg)
        console.print("[bold green]✔ Режим сохранен![/bold green]")
        time.sleep(1)
    elif ch == "2":
        new_url = Prompt.ask("Введите новую ссылку или код", default=cfg.get("referral_url"))
        cfg["referral_url"] = new_url
        if "start=" in new_url:
            cfg["referral_code"] = new_url.split("start=")[-1].strip()
        else:
            cfg["referral_code"] = new_url.strip()
        save_config(cfg)
        console.print("[bold green]✔ Ссылка основы сохранена![/bold green]")
        time.sleep(1)
    elif ch == "4":
        new_max = IntPrompt.ask("Сколько рефералов на аккаунт? (1, 2, 3 или 4)", default=cfg.get("max_referrals_per_account", 1))
        cfg["max_referrals_per_account"] = new_max
        save_config(cfg)
        console.print(f"[bold green]✔ Теперь каждый аккаунт будет получать {new_max} реф.![/bold green]")
        time.sleep(1)

def show_withdrawals_history():
    render_banner()
    w_file = "withdrawals.json"
    if not os.path.exists(w_file):
        console.print("[yellow]История выплат пуста.[/yellow]")
        Prompt.ask("\nНажмите Enter для возврата в меню")
        return
    
    try:
        w_list = json.load(open(w_file, "r", encoding="utf-8"))
    except Exception:
        w_list = []
        
    if not w_list:
        console.print("[yellow]История выплат пуста.[/yellow]")
        Prompt.ask("\nНажмите Enter для возврата в меню")
        return

    table = Table(title="🎫 Полученные чеки выплат CryptoBot (USDT)", border_style="green")
    table.add_column("№", style="dim", width=3)
    table.add_column("Аккаунт-донор", style="cyan")
    table.add_column("Сумма", style="bold green", justify="right")
    table.add_column("Ссылка на чек (CryptoBot)", style="bold yellow")
    table.add_column("Зачислено на", style="bold cyan")
    table.add_column("Дата", style="dim white")

    total_sum = 0.0
    for i, item in enumerate(w_list, 1):
        amt = float(item.get("amount", 0.0))
        total_sum += amt
        dt_str = item.get("timestamp", "")[:16].replace("T", " ")
        claimed = item.get("claimed_by", "-")
        cl_short = claimed[:18] if claimed else "-"
        table.add_row(
            str(i),
            str(item.get("account"))[:22],
            f"${amt:.2f}",
            str(item.get("check_url")),
            cl_short,
            dt_str
        )

    console.print(table)
    console.print(f"\n[bold green]Всего выведено чеками:[/bold green] [bold yellow]${total_sum:.2f}[/bold yellow] ({len(w_list)} чеков)")
    Prompt.ask("\nНажмите Enter для возврата в меню")

async def main():
    while True:
        render_banner()
        console.print("[bold cyan]1.[/bold cyan] 🚀 [bold green]Запустить фарм (с пирамидой и защитой от спайков)[/bold green]")
        console.print("[bold cyan]2.[/bold cyan] 📊 [bold yellow]Живой аудит фермы: балансы, таймеры и авто-очистка[/bold yellow]")
        console.print("[bold cyan]3.[/bold cyan] 🌳 [bold green]Дерево рефералов и структура пирамиды[/bold green]")
        console.print("[bold cyan]4.[/bold cyan] 🔄 [bold blue]Синхронизировать сессии из TG_farm[/bold blue]")
        console.print("[bold cyan]5.[/bold cyan] 💸 [bold magenta]Автоматический вывод (живой анализ и сбор в CryptoBot)[/bold magenta]")
        console.print("[bold cyan]6.[/bold cyan] 🎫 [bold green]Список выведенных чеков CryptoBot (withdrawals.json)[/bold green]")
        console.print("[bold cyan]7.[/bold cyan] ⚙️ [bold white]Настройки (пирамида, задержки, пачки, получатель)[/bold white]")
        console.print("[bold cyan]0.[/bold cyan] 🚪 [dim white]Выход[/dim white]\n")

        choice = Prompt.ask("[bold yellow]Выберите пункт[/bold yellow]", choices=["1", "2", "3", "4", "5", "6", "7", "0"], default="2")

        if choice == "1":
            await run_farm_mode()
        elif choice == "2":
            await show_database_stats()
        elif choice == "3":
            show_referral_tree()
        elif choice == "4":
            accounts = sync_sessions()
            console.print(f"[bold green]✔ Синхронизировано {len(accounts)} сессий в Pacocash\\sessions![/bold green]")
            time.sleep(1.5)
        elif choice == "5":
            await run_withdrawal_mode()
        elif choice == "6":
            show_withdrawals_history()
        elif choice == "7":
            settings_menu()
        elif choice == "0":
            console.print("[bold yellow]До свидания![/bold yellow]")
            break

if __name__ == "__main__":
    asyncio.run(main())
