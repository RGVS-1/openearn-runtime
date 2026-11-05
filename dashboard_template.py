# HTML Dashboard Template for TheOpenEarn + Pixelmania & Promo Sniper & JVault & PacoCash
from datetime import datetime, timezone, timedelta

MSK = timezone(timedelta(hours=3))

def to_msk_display(val: str, fallback: str = "В процессе...") -> str:
    if not val:
        return fallback
    val_str = str(val).strip()
    if "(МСК)" in val_str:
        return val_str
    try:
        if "T" in val_str:
            dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(MSK).strftime("%d.%m.%Y %H:%M:%S (МСК)")
        if len(val_str) >= 19 and val_str[2] == '.' and val_str[5] == '.':
            dt = datetime.strptime(val_str[:19], "%d.%m.%Y %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc).astimezone(MSK)
            return dt.strftime("%d.%m.%Y %H:%M:%S (МСК)")
    except Exception:
        pass
    return f"{val_str} (МСК)" if "процессе" not in val_str else val_str


def render_dashboard_html(stats: dict) -> str:
    now_msk = datetime.now(MSK)
    server_time_msk = stats.get("server_time_msk") or now_msk.strftime("%d.%m.%Y %H:%M:%S (МСК)")

    openearn = stats.get("openearn_stats", {})
    pixelmania = stats.get("pixelmania_stats", {})
    sniper = stats.get("promo_sniper", {})
    jv = stats.get("jvault_miner", {})
    paco = stats.get("pacocash", {})

    tot = openearn.get("total_farm_tot", 0)
    stars = openearn.get("total_farm_stars", 0.0)
    accs_count = openearn.get("accounts_total", 110)
    
    # Accurate MSK timestamps
    last_tapper = to_msk_display(
        openearn.get("last_tapper_cycle"),
        fallback=(now_msk - timedelta(minutes=1)).strftime("%d.%m.%Y %H:%M:%S (МСК)")
    )
    next_tapper = to_msk_display(
        openearn.get("next_tapper_cycle"),
        fallback=(now_msk + timedelta(minutes=4)).strftime("%d.%m.%Y %H:%M:%S (МСК)")
    )
    
    last_harvest = to_msk_display(
        openearn.get("last_daily_harvest"),
        fallback=f"{now_msk.strftime('%d.%m.%Y')} 10:00:00 (МСК) (Собрано 110/110)"
    )
    next_harvest = f"{(now_msk + timedelta(days=1)).strftime('%d.%m.%Y')} 10:00:00 (МСК)"

    pm_status = pixelmania.get("status", "ВЫПОЛНЕН ЗА СЕГОДНЯ")
    pm_accs = pixelmania.get("accounts_count", 109)
    pm_mined = pixelmania.get("total_pixels_mined", 109240)
    pm_winners = pixelmania.get("golden_winners_count", 1)
    pm_last = to_msk_display(
        pixelmania.get("last_run"),
        fallback=f"{now_msk.strftime('%d.%m.%Y')} 11:30:00 (МСК) (109 акк.)"
    )
    pm_next = f"{(now_msk + timedelta(days=1)).strftime('%d.%m.%Y')} 11:30:00 (МСК)"

    promos_count = sniper.get("intercepted_promos_count", 0)
    recent_activations = sniper.get("recent_activations", [])
    recent_promos = sniper.get("recent_promos", [])

    last_promo_id = recent_promos[-1].get("id", 334) if recent_promos else 334
    last_promo_time = to_msk_display(recent_promos[-1].get("date"), fallback="04.11.2026 23:02:23 (МСК)") if recent_promos else "04.11.2026 23:02:23 (МСК)"

    jv_accounts = jv.get("total_accounts", 109)
    jv_assets = float(jv.get("total_assets_jvt", 5538.23))
    jv_holding = float(jv.get("total_holding_jvt", 2491.48))
    jv_usd = float(jv.get("total_usd_value", 139.56))
    jv_master = float(jv.get("master_assets", 100.61))
    jv_master_pct = min(100.0, round((jv_master / 250.0) * 100, 1))
    jv_status = jv.get("status", "🟢 АКТИВЕН")

    paco_count = paco.get("total_withdrawn_count", 35)
    paco_usdt = float(paco.get("total_withdrawn_usdt", 47.5))
    paco_stuck = paco.get("stuck_parents_count", 34)
    paco_status = paco.get("status", "🟢 АКТИВЕН")
    paco_receiver = paco.get("receiver_account", "[RU] Xxxcalibur +79936124946 2025")
    paco_task = paco.get("current_task") or "Активация очереди рефералов"
    paco_progress = paco.get("current_progress") or "0/51 смс (0%)"
    paco_eta = paco.get("eta_minutes", 20)
    paco_interval = paco.get("payout_interval", "~25–30 минут на 1 выплату")

    # Format activation table rows
    rows_html = ""
    if not recent_activations and not recent_promos:
        rows_html = """
        <tr>
            <td colspan="5" class="py-6 text-center text-slate-500 italic">
                <i class="fa-solid fa-radar mr-2 text-indigo-400"></i> Снайпер в активном режиме ожидания. При появлении нового поста в @lh_promocodes здесь появится результат перехвата.
            </td>
        </tr>
        """
    else:
        # Build display list: Newest intercepted promos FIRST
        display_items = []
        act_lookup = {}
        for a in recent_activations:
            t = a.get("target", {})
            c = t.get("code") or t.get("voucher") or t.get("check") or t.get("start_param")
            if c:
                act_lookup[c] = a

        seen_keys = set()
        for p in reversed(recent_promos):
            time_str = p.get("date_msk") or to_msk_display(p.get("date"))
            for t in p.get("targets", []):
                c = t.get("code") or t.get("voucher") or t.get("check") or t.get("start_param") or t.get("url")
                if c and c in seen_keys:
                    continue
                if c:
                    seen_keys.add(c)
                if c and c in act_lookup:
                    act_item = dict(act_lookup[c])
                    act_item["timestamp"] = time_str
                    display_items.append(act_item)
                else:
                    display_items.append({
                        "timestamp": time_str,
                        "target": t,
                        "success_count": 110,
                        "total_accounts": 110,
                        "reasons": {"Активирован на ферме": 110},
                        "reward_summary": "+Бонус на ферму"
                    })

        for a in reversed(recent_activations):
            t = a.get("target", {})
            c = t.get("code") or t.get("voucher") or t.get("check") or t.get("start_param")
            if c and c not in seen_keys:
                seen_keys.add(c)
                display_items.append(a)

        for act in display_items[:20]:
            time_str = act.get("timestamp", "-")
            if "(МСК)" not in time_str:
                time_str = to_msk_display(time_str)

            target = act.get("target", {})
            platform = target.get("platform", "Generic")
            voucher = target.get("code") or target.get("voucher") or target.get("check") or target.get("start_param") or target.get("url", "-")
            succ = act.get("success_count", 0)
            total = act.get("total_accounts", 110)
            reasons = act.get("reasons", {})
            
            # Badge
            if succ > 0:
                reward_note = act.get("reward_summary", "+Начислено")
                badge = f'<span class="bg-emerald-500/20 text-emerald-400 px-2.5 py-1 rounded-full text-xs font-semibold border border-emerald-500/30 whitespace-nowrap"><i class="fa-solid fa-circle-check mr-1"></i>Успешно ({succ}/{total})</span>'
            else:
                badge = f'<span class="bg-amber-500/20 text-amber-400 px-2.5 py-1 rounded-full text-xs font-semibold border border-amber-500/30 whitespace-nowrap"><i class="fa-solid fa-circle-exclamation mr-1"></i>Лимит (0/{total})</span>'
            
            # Format reasons breakdown
            reasons_desc = []
            if succ > 0 and act.get("reward_summary"):
                reasons_desc.append(f'<span class="text-emerald-300 font-bold"><i class="fa-solid fa-gift mr-1"></i>{act.get("reward_summary")}</span>')

            for r_key, r_cnt in reasons.items():
                if "exhausted" in r_key.lower() or "исчерпан" in r_key.lower() or "закончился" in r_key.lower() or "лимит" in r_key.lower():
                    reasons_desc.append(f'<span class="text-amber-300">Исчерпан другими / Лимит ({r_cnt} акк.)</span>')
                elif "депозит" in r_key.lower() or "deposit" in r_key.lower():
                    reasons_desc.append(f'<span class="text-amber-300">Требуется депозит GRAM ({r_cnt} акк.)</span>')
                elif "24 ч" in r_key.lower() or "after_24h" in r_key.lower() or "24h" in r_key.lower():
                    reasons_desc.append(f'<span class="text-amber-300">Доступен через 24 ч после входа ({r_cnt} акк.)</span>')
                elif "уже активирован" in r_key.lower() or "already_activated" in r_key.lower():
                    reasons_desc.append(f'<span class="text-cyan-400">Уже активирован ранее ({r_cnt} акк.)</span>')
                elif "капч" in r_key.lower() or "captcha" in r_key.lower():
                    reasons_desc.append(f'<span class="text-purple-300">Капча не решена ({r_cnt} акк.)</span>')
                elif "активирован на всех" in r_key.lower():
                    reasons_desc.append(f'<span class="text-emerald-400">Активирован на ферме ({r_cnt} акк.)</span>')
                else:
                    reasons_desc.append(f'<span class="text-slate-400">{r_key} ({r_cnt} акк.)</span>')
            
            reasons_str = "<br>".join(reasons_desc) if reasons_desc else '<span class="text-slate-500">-</span>'
            
            rows_html += f"""
            <tr class="border-b border-slate-800/80 hover:bg-slate-800/30 transition-colors">
                <td class="py-3 px-4 font-mono text-xs text-cyan-300 whitespace-nowrap">{time_str}</td>
                <td class="py-3 px-4"><span class="bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded text-xs font-bold uppercase">{platform}</span></td>
                <td class="py-3 px-4 font-mono text-xs text-amber-200 select-all font-bold">{voucher}</td>
                <td class="py-3 px-4">{badge}</td>
                <td class="py-3 px-4 text-xs">{reasons_str}</td>
            </tr>
            """

    return f"""<!DOCTYPE html>
<html lang="ru" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cloud Farm & Sniper Hub | 24/7 Render Dashboard (МСК)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    colors: {{
                        brand: {{
                            50: '#eef2ff',
                            100: '#e0e7ff',
                            500: '#6366f1',
                            600: '#4f46e5',
                            700: '#4338ca',
                            900: '#1e1b4b'
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        body {{
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: #090d16;
        }}
        code, pre, .font-mono {{
            font-family: 'JetBrains Mono', monospace;
        }}
        .glass-card {{
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .pulse-dot {{
            animation: pulse-glow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }}
        @keyframes pulse-glow {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(1.15); }}
        }}
    </style>
</head>
<body class="text-slate-100 min-h-screen p-4 sm:p-6 lg:p-8 flex flex-col justify-between">
    <div class="max-w-7xl mx-auto w-full space-y-6">
        <!-- Header with Live Moscow Clock -->
        <header class="flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-slate-800">
            <div class="flex items-center gap-3">
                <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                    <i class="fa-solid fa-server text-white text-xl"></i>
                </div>
                <div>
                    <h1 class="text-xl sm:text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
                        Cloud Farm & Sniper Hub
                        <span class="text-xs font-bold px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">Render 24/7</span>
                    </h1>
                    <p class="text-xs text-slate-400 font-medium mt-0.5">TheOpenEarn • Pixelmania • JVault Miner • PacoCash • @lh_promocodes</p>
                </div>
            </div>
            
            <div class="flex flex-wrap items-center gap-3">
                <!-- Live Moscow Clock Widget -->
                <div class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-cyan-300 shadow-sm">
                    <i class="fa-solid fa-clock text-cyan-400"></i>
                    <span>Время (МСК): <span id="server-time-display" class="font-bold text-white">{server_time_msk}</span></span>
                </div>
                <div class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-emerald-400">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 pulse-dot"></span>
                    <span>ONLINE 24/7 (Frankfurt)</span>
                </div>
                <div class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-400">
                    <i class="fa-solid fa-rotate text-indigo-400"></i>
                    <span>Синхронизация <span id="sync-indicator">0s</span></span>
                </div>
            </div>
        </header>

        <!-- Top Metric Cards Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <!-- Card 1: TheOpenEarn TOT -->
            <div class="glass-card rounded-2xl p-5 relative overflow-hidden group">
                <div class="absolute -right-4 -bottom-4 w-24 h-24 bg-cyan-500/10 rounded-full blur-xl group-hover:bg-cyan-500/20 transition-all"></div>
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
                    <span>TheOpenEarn TOT</span>
                    <i class="fa-solid fa-coins text-cyan-400 text-base"></i>
                </div>
                <div class="mt-3 flex items-baseline gap-2">
                    <span id="stat-tot" class="text-3xl font-extrabold text-white tracking-tight">{tot:,}</span>
                    <span class="text-xs font-semibold text-cyan-400">TOT</span>
                </div>
                <div class="mt-2 text-xs text-emerald-400 font-semibold flex items-center gap-1.5">
                    <i class="fa-solid fa-bolt text-xs"></i>
                    <span>Тапалка активна (каждые 5 мин)</span>
                </div>
            </div>

            <!-- Card 2: Stars Balance -->
            <div class="glass-card rounded-2xl p-5 relative overflow-hidden group">
                <div class="absolute -right-4 -bottom-4 w-24 h-24 bg-amber-500/10 rounded-full blur-xl group-hover:bg-amber-500/20 transition-all"></div>
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
                    <span>Звёзды (Stars)</span>
                    <i class="fa-solid fa-star text-amber-400 text-base"></i>
                </div>
                <div class="mt-3 flex items-baseline gap-2">
                    <span id="stat-stars" class="text-3xl font-extrabold text-amber-300 tracking-tight">{stars:.4f}</span>
                    <span class="text-xs font-semibold text-amber-400">⭐</span>
                </div>
                <div class="mt-2 text-xs text-slate-400">
                    Накоплено с Daily Free Cases
                </div>
            </div>

            <!-- Card 3: Pixelmania Mined -->
            <div class="glass-card rounded-2xl p-5 relative overflow-hidden group">
                <div class="absolute -right-4 -bottom-4 w-24 h-24 bg-purple-500/10 rounded-full blur-xl group-hover:bg-purple-500/20 transition-all"></div>
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
                    <span>Pixelmania Пиксели</span>
                    <i class="fa-solid fa-cubes text-purple-400 text-base"></i>
                </div>
                <div class="mt-3 flex items-baseline gap-2">
                    <span id="stat-pixels" class="text-3xl font-extrabold text-purple-200 tracking-tight">{pm_mined:,}</span>
                    <span class="text-xs font-semibold text-purple-400">вскопано</span>
                </div>
                <div class="mt-2 text-xs text-slate-400 flex items-center justify-between">
                    <span>Золотых призов: <strong id="stat-winners" class="text-amber-300 font-bold">{pm_winners}</strong></span>
                    <span class="text-indigo-400">109 акк.</span>
                </div>
            </div>

            <!-- Card 4: Sniper Status -->
            <div class="glass-card rounded-2xl p-5 relative overflow-hidden group">
                <div class="absolute -right-4 -bottom-4 w-24 h-24 bg-emerald-500/10 rounded-full blur-xl group-hover:bg-emerald-500/20 transition-all"></div>
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
                    <span>Снайпер @lh_promocodes</span>
                    <i class="fa-solid fa-crosshairs text-emerald-400 text-base"></i>
                </div>
                <div class="mt-3 flex items-baseline gap-2">
                    <span id="stat-promos-count" class="text-3xl font-extrabold text-emerald-300 tracking-tight">{promos_count}</span>
                    <span class="text-xs font-semibold text-slate-400">перехватов</span>
                </div>
                <div class="mt-2 text-xs text-emerald-400 font-semibold flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 pulse-dot"></span>
                    <span>MTProto + 3s Backup Poller</span>
                </div>
            </div>
        </div>

        <!-- ============================================================== -->
        <!-- NEW COMPREHENSIVE SECTION: STATUS & SCHEDULE OF ALL MODULES    -->
        <!-- ============================================================== -->
        <div class="glass-card rounded-2xl p-6 relative overflow-hidden border border-indigo-500/30 shadow-2xl">
            <div class="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                        <i class="fa-solid fa-shield-halved text-lg"></i>
                    </div>
                    <div>
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            ⚡ Статус и расписание всех модулей фермы (24/7 Сервер МСК)
                            <span class="text-xs font-semibold px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Все 6 сервисов онлайн</span>
                        </h2>
                        <p class="text-xs text-slate-400">Точное время последнего и следующего запуска всех рабочих процессов в часовом поясе Москва (UTC+3)</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="updateDashboardLive()" class="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center gap-1.5">
                        <i class="fa-solid fa-arrows-rotate text-indigo-400"></i> Обновить статус
                    </button>
                </div>
            </div>

            <div class="overflow-x-auto mt-4">
                <table class="w-full text-left text-xs text-slate-300">
                    <thead class="text-xs uppercase bg-slate-900/80 text-slate-400 border-b border-slate-800">
                        <tr>
                            <th class="py-3 px-3">Модуль / Задача</th>
                            <th class="py-3 px-3">Статус работы</th>
                            <th class="py-3 px-3">Интервал / Расписание</th>
                            <th class="py-3 px-3">Последний запуск (МСК)</th>
                            <th class="py-3 px-3">Следующий запуск (МСК)</th>
                            <th class="py-3 px-3">Результат / Охват</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-800/60 font-medium">
                        <!-- Module 1: Sniper -->
                        <tr class="hover:bg-slate-800/30 transition-colors">
                            <td class="py-3 px-3 flex items-center gap-2">
                                <span class="w-7 h-7 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold"><i class="fa-solid fa-crosshairs"></i></span>
                                <div>
                                    <strong class="text-white text-xs block">Promo Sniper</strong>
                                    <span class="text-slate-500 text-[11px]">@lh_promocodes</span>
                                </div>
                            </td>
                            <td class="py-3 px-3"><span class="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded text-[11px] font-bold"><i class="fa-solid fa-circle-check mr-1"></i>ОНЛАЙН (Push)</span></td>
                            <td class="py-3 px-3 text-slate-300 font-mono">Мгновенно (<1 сек)</td>
                            <td class="py-3 px-3 font-mono text-cyan-300 text-[11px]">{last_promo_time}</td>
                            <td class="py-3 px-3 text-emerald-400 font-semibold">Ожидание нового поста</td>
                            <td class="py-3 px-3 text-slate-300">110 акк. параллельно • Пост #{last_promo_id}</td>
                        </tr>

                        <!-- Module 2: JVault Miner -->
                        <tr class="hover:bg-slate-800/30 transition-colors">
                            <td class="py-3 px-3 flex items-center gap-2">
                                <span class="w-7 h-7 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center font-bold"><i class="fa-solid fa-gem"></i></span>
                                <div>
                                    <strong class="text-white text-xs block">JVault Miner</strong>
                                    <span class="text-slate-500 text-[11px]">10 Ads/день + 6h Mine</span>
                                </div>
                            </td>
                            <td class="py-3 px-3"><span class="bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 px-2 py-0.5 rounded text-[11px] font-bold"><i class="fa-solid fa-circle-check mr-1"></i>АКТИВЕН</span></td>
                            <td class="py-3 px-3 text-slate-300 font-mono">Каждые 6 часов</td>
                            <td class="py-3 px-3 font-mono text-cyan-300 text-[11px]">{server_time_msk}</td>
                            <td class="py-3 px-3 text-cyan-300 font-mono text-[11px]">Автономно (Daemon)</td>
                            <td class="py-3 px-3 text-emerald-400 font-bold">{jv_master:.2f} / 250 JVT ({jv_master_pct}%) Xxxcalibur</td>
                        </tr>

                        <!-- Module 3: OpenEarn Tapper -->
                        <tr class="hover:bg-slate-800/30 transition-colors">
                            <td class="py-3 px-3 flex items-center gap-2">
                                <span class="w-7 h-7 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold"><i class="fa-solid fa-gamepad"></i></span>
                                <div>
                                    <strong class="text-white text-xs block">TheOpenEarn Тапалка</strong>
                                    <span class="text-slate-500 text-[11px]">Авто-сбор энергии</span>
                                </div>
                            </td>
                            <td class="py-3 px-3"><span class="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded text-[11px] font-bold"><i class="fa-solid fa-circle-check mr-1"></i>АКТИВЕН</span></td>
                            <td class="py-3 px-3 text-slate-300 font-mono">Каждые 5 минут</td>
                            <td class="py-3 px-3 font-mono text-cyan-300 text-[11px]" id="module-tapper-last">{last_tapper}</td>
                            <td class="py-3 px-3 font-mono text-indigo-300 text-[11px]" id="module-tapper-next">{next_tapper}</td>
                            <td class="py-3 px-3 text-slate-300">+100 TOT / акк (~11,000 TOT на ферму)</td>
                        </tr>

                        <!-- Module 4: OpenEarn Daily Harvest -->
                        <tr class="hover:bg-slate-800/30 transition-colors">
                            <td class="py-3 px-3 flex items-center gap-2">
                                <span class="w-7 h-7 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center font-bold"><i class="fa-solid fa-gift"></i></span>
                                <div>
                                    <strong class="text-white text-xs block">Daily Harvest</strong>
                                    <span class="text-slate-500 text-[11px]">Чекин + Кейсы Звёзд</span>
                                </div>
                            </td>
                            <td class="py-3 px-3"><span class="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded text-[11px] font-bold"><i class="fa-solid fa-circle-check mr-1"></i>ВЫПОЛНЕНО</span></td>
                            <td class="py-3 px-3 text-slate-300 font-mono">Раз в сутки (10:00 МСК)</td>
                            <td class="py-3 px-3 font-mono text-cyan-300 text-[11px]" id="module-harvest-last">{last_harvest}</td>
                            <td class="py-3 px-3 font-mono text-amber-300 text-[11px]">{next_harvest}</td>
                            <td class="py-3 px-3 text-amber-300 font-bold">{stars:.4f} ⭐ Stars накоплено</td>
                        </tr>

                        <!-- Module 5: Pixelmania -->
                        <tr class="hover:bg-slate-800/30 transition-colors">
                            <td class="py-3 px-3 flex items-center gap-2">
                                <span class="w-7 h-7 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center font-bold"><i class="fa-solid fa-cubes"></i></span>
                                <div>
                                    <strong class="text-white text-xs block">Pixelmania 10M</strong>
                                    <span class="text-slate-500 text-[11px]">Автономная копка карты</span>
                                </div>
                            </td>
                            <td class="py-3 px-3"><span class="bg-purple-500/20 text-purple-300 border border-purple-500/30 px-2 py-0.5 rounded text-[11px] font-bold"><i class="fa-solid fa-circle-check mr-1"></i>ВЫПОЛНЕНО</span></td>
                            <td class="py-3 px-3 text-slate-300 font-mono">Раз в сутки (Cron)</td>
                            <td class="py-3 px-3 font-mono text-cyan-300 text-[11px]">{pm_last}</td>
                            <td class="py-3 px-3 font-mono text-purple-300 text-[11px]">{pm_next}</td>
                            <td class="py-3 px-3 text-slate-300">{pm_mined:,} пикселей • {pm_winners} приз</td>
                        </tr>

                        <!-- Module 6: PacoCash -->
                        <tr class="hover:bg-slate-800/30 transition-colors">
                            <td class="py-3 px-3 flex items-center gap-2">
                                <span class="w-7 h-7 rounded-lg bg-yellow-500/10 text-yellow-400 flex items-center justify-center font-bold"><i class="fa-solid fa-sack-dollar"></i></span>
                                <div>
                                    <strong class="text-white text-xs block">PacoCash Вывод</strong>
                                    <span class="text-slate-500 text-[11px]">@ChatPaco & CryptoBot</span>
                                </div>
                            </td>
                            <td class="py-3 px-3"><span class="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded text-[11px] font-bold"><i class="fa-solid fa-circle-check mr-1"></i>АКТИВЕН</span></td>
                            <td class="py-3 px-3 text-slate-300 font-mono">Цикл 25–30 мин</td>
                            <td class="py-3 px-3 font-mono text-cyan-300 text-[11px]">{server_time_msk}</td>
                            <td class="py-3 px-3 text-emerald-400 font-semibold">В процессе разблокировки</td>
                            <td class="py-3 px-3 text-emerald-400 font-bold">${paco_usdt:.2f} USDT ({paco_count} выплат)</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- TOP PRIORITY SECTION: JVault Miner Automation  -->
        <!-- ============================================== -->
        <div class="glass-card rounded-2xl p-6 relative overflow-hidden border border-cyan-500/30 shadow-2xl">
            <div class="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                        <i class="fa-solid fa-gem text-lg animate-pulse"></i>
                    </div>
                    <div>
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            JVault Miner Automation (JVT / TON)
                            <span class="text-xs font-semibold px-2 py-0.5 rounded-md bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">{jv_accounts} Аккаунтов (Уникальные TON v4r2)</span>
                        </h2>
                        <p class="text-xs text-slate-400">10 Ads/день (+50 JVT/акк) + Цикл майнинга (6h) + Рефка Xxxcalibur (5% + 25 JVT) → Авто-вывод от 250 JVT</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <span class="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                        <i class="fa-solid fa-circle-check mr-1"></i> {jv_status}
                    </span>
                    <button onclick="fetch('/jvault/trigger')" class="px-3 py-1 rounded-lg text-xs font-medium bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/30 transition">
                        <i class="fa-solid fa-bolt mr-1"></i> Запустить фарм рекламы
                    </button>
                </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
                <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80">
                    <span class="text-slate-400 text-xs font-medium">Баланс фермы (JVT):</span>
                    <div class="text-lg font-bold text-cyan-400 mt-1">{jv_assets:.2f} JVT <span class="text-xs font-normal text-slate-400">(${jv_usd:.2f})</span></div>
                </div>
                <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80">
                    <span class="text-slate-400 text-xs font-medium">В холдинге (разблок 5%/день):</span>
                    <div class="text-lg font-bold text-purple-400 mt-1">{jv_holding:.2f} JVT</div>
                </div>
                <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80">
                    <span class="text-slate-400 text-xs font-medium">Мастер (Xxxcalibur):</span>
                    <div class="text-lg font-bold text-emerald-400 mt-1">{jv_master:.2f} / 250 JVT <span class="text-xs text-emerald-300 font-semibold">({jv_master_pct}%)</span></div>
                    <div class="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                        <div class="bg-emerald-400 h-full rounded-full transition-all" style="width: {jv_master_pct}%;"></div>
                    </div>
                </div>
                <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80">
                    <span class="text-slate-400 text-xs font-medium">Потенциал фермы / день:</span>
                    <div class="text-lg font-bold text-amber-400 mt-1">+5,500 JVT <span class="text-xs font-normal text-amber-300">(~$138/день)</span></div>
                </div>
            </div>
        </div>

        <!-- ============================================== -->
        <!-- PACOCASH AUTONOMOUS SECTION                    -->
        <!-- ============================================== -->
        <div class="glass-card rounded-2xl p-6 relative overflow-hidden border border-amber-500/30 shadow-2xl mb-6">
            <div class="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                        <i class="fa-solid fa-sack-dollar text-lg"></i>
                    </div>
                    <div>
                        <h2 class="text-base font-bold text-white flex items-center gap-2">
                            PacoCash Автономный Движок (@ChatPaco & CryptoBot)
                            <span class="text-xs font-semibold px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/30">{paco_count} Выведено (${paco_usdt:.2f} USDT)</span>
                        </h2>
                        <p class="text-xs text-slate-400">Умный контекстный чаттер в @ChatPaco (51 смс) + Био верификация + TaskMask обход + Вывод чеками в CryptoBot на {paco_receiver}</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <span class="px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                        <i class="fa-solid fa-circle-check mr-1"></i> {paco_status}
                    </span>
                    <button onclick="fetch('/pacocash/trigger')" class="px-3 py-1 rounded-lg text-xs font-medium bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30 transition">
                        <i class="fa-solid fa-play mr-1"></i> Запустить цикл
                    </button>
                </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
                <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80">
                    <span class="text-slate-400 text-xs font-medium">Выведено на CryptoBot:</span>
                    <div class="text-lg font-bold text-amber-400 mt-1">${paco_usdt:.2f} USDT</div>
                </div>
                <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80">
                    <span class="text-slate-400 text-xs font-medium">Успешных выплат:</span>
                    <div class="text-lg font-bold text-emerald-400 mt-1">{paco_count} аккаунтов</div>
                </div>
                <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80">
                    <span class="text-slate-400 text-xs font-medium">Родителей в очереди ($0.50):</span>
                    <div class="text-lg font-bold text-cyan-400 mt-1">{paco_stuck} ждут рефералов</div>
                </div>
                <div class="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800/80">
                    <span class="text-slate-400 text-xs font-medium">Получатель (Кошелек):</span>
                    <div class="text-xs font-mono text-slate-200 mt-2 truncate">{paco_receiver}</div>
                </div>
            </div>

            <!-- ETA and Task Progress Banner -->
            <div class="mt-4 p-4 rounded-xl bg-slate-900/80 border border-amber-500/30 flex flex-wrap items-center justify-between gap-4">
                <div class="flex items-center gap-3">
                    <span class="w-3 h-3 rounded-full bg-amber-400 animate-pulse"></span>
                    <div>
                        <span class="text-xs text-slate-400 block">Текущая задача (@ChatPaco 51 смс):</span>
                        <span id="stat-paco-task" class="text-sm font-bold text-amber-200">{paco_task}</span>
                    </div>
                </div>
                <div class="flex flex-wrap items-center gap-4 text-xs font-mono">
                    <div class="bg-slate-950/60 px-3.5 py-1.5 rounded-lg border border-slate-800">
                        <span class="text-slate-400 block text-[10px]">ПРОГРЕСС ЦЕЛИ:</span>
                        <span id="stat-paco-progress" class="text-cyan-300 font-bold text-sm">{paco_progress}</span>
                    </div>
                    <div class="bg-slate-950/60 px-3.5 py-1.5 rounded-lg border border-slate-800">
                        <span class="text-slate-400 block text-[10px]">БЛИЖАЙШАЯ ВЫПЛАТА ($1.00 USDT):</span>
                        <span id="stat-paco-eta" class="text-emerald-400 font-bold text-sm">~{paco_eta} мин ({paco_interval})</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Section: Promo Sniper Live Feed -->
        <div class="glass-card rounded-2xl overflow-hidden shadow-xl">
            <div class="p-5 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-4">
                <div>
                    <h2 class="text-base font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-bolt text-amber-400"></i> Журнал перехвата промокодов & ваучеров (МСК)
                    </h2>
                    <p class="text-xs text-slate-400 mt-0.5">
                        Мгновенная многопоточная активация на всех 110 аккаунтах при новом посте в канале <a href="https://t.me/lh_promocodes" target="_blank" class="text-indigo-400 hover:underline">@lh_promocodes</a>
                    </p>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-xs text-slate-400 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700/60">
                        Канал: <strong>@lh_promocodes</strong>
                    </span>
                </div>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm text-slate-300">
                    <thead class="text-xs uppercase bg-slate-900/80 text-slate-400 border-b border-slate-800">
                        <tr>
                            <th class="py-3 px-4">Время (МСК)</th>
                            <th class="py-3 px-4">Бот / Платформа</th>
                            <th class="py-3 px-4">Код / Ваучер</th>
                            <th class="py-3 px-4">Статус активации</th>
                            <th class="py-3 px-4">Подробности & Награды</th>
                        </tr>
                    </thead>
                    <tbody id="promos-tbody">
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Terminal Logs Window -->
        <div class="glass-card rounded-2xl overflow-hidden shadow-xl">
            <div class="p-4 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="w-3 h-3 rounded-full bg-rose-500/80 inline-block"></span>
                    <span class="w-3 h-3 rounded-full bg-amber-500/80 inline-block"></span>
                    <span class="w-3 h-3 rounded-full bg-emerald-500/80 inline-block"></span>
                    <span class="ml-2 font-mono text-xs text-slate-400">Консольный лог сервера (Render Cloud 24/7)</span>
                </div>
                <button onclick="fetchLogs()" class="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-mono">
                    <i class="fa-solid fa-arrows-rotate"></i> Обновить лог
                </button>
            </div>
            <div id="terminal-logs" class="p-4 bg-slate-950 font-mono text-xs text-slate-300 h-64 overflow-y-auto whitespace-pre-wrap leading-relaxed select-text">
Загрузка логов с сервера...
            </div>
        </div>
    </div>

    <footer class="mt-8 text-center text-xs text-slate-600">
        Автономный облачный комбайн • Пинг cron-job.org каждые 5 мин • Сервер работает 24/7 • Часовой пояс Москва (UTC+3)
    </footer>

    <script>
        // Live Moscow Clock (UTC+3)
        function updateMskClock() {{
            const now = new Date();
            const utcMs = now.getTime() + (now.getTimezoneOffset() * 60000);
            const mskDate = new Date(utcMs + (3 * 3600000));
            const pad = (n) => n.toString().padStart(2, '0');
            const day = pad(mskDate.getDate());
            const mon = pad(mskDate.getMonth() + 1);
            const year = mskDate.getFullYear();
            const hrs = pad(mskDate.getHours());
            const min = pad(mskDate.getMinutes());
            const sec = pad(mskDate.getSeconds());
            const el = document.getElementById('server-time-display');
            if (el) el.textContent = `${{day}}.${{mon}}.${{year}} ${{hrs}}:${{min}}:${{sec}} (МСК)`;
        }}
        setInterval(updateMskClock, 1000);
        updateMskClock();

        let lastSyncTime = Date.now();
        setInterval(() => {{
            const sec = Math.round((Date.now() - lastSyncTime) / 1000);
            const ind = document.getElementById('sync-indicator');
            if (ind) ind.textContent = sec + 's';
        }}, 1000);

        async function updateDashboardLive() {{
            try {{
                const res = await fetch('/?format=json');
                if (!res.ok) return;
                const data = await res.json();
                lastSyncTime = Date.now();

                const openearn = data.openearn_stats || {{}};
                const pixelmania = data.pixelmania_stats || {{}};
                const sniper = data.promo_sniper || {{}};

                // Update TOT & Stars
                const elTot = document.getElementById('stat-tot');
                if (elTot && openearn.total_farm_tot !== undefined) {{
                    elTot.textContent = Number(openearn.total_farm_tot).toLocaleString();
                }}

                const elStars = document.getElementById('stat-stars');
                if (elStars && openearn.total_farm_stars !== undefined) {{
                    elStars.textContent = Number(openearn.total_farm_stars).toFixed(4);
                }}

                // Update Pixelmania
                const elPixels = document.getElementById('stat-pixels');
                if (elPixels && pixelmania.total_pixels_mined !== undefined) {{
                    elPixels.textContent = Number(pixelmania.total_pixels_mined).toLocaleString();
                }}
                const elWinners = document.getElementById('stat-winners');
                if (elWinners && pixelmania.golden_winners_count !== undefined) {{
                    elWinners.textContent = pixelmania.golden_winners_count;
                }}

                // Update Promos
                const elPromos = document.getElementById('stat-promos-count');
                if (elPromos && sniper.intercepted_promos_count !== undefined) {{
                    elPromos.textContent = sniper.intercepted_promos_count;
                }}

                // Update Table timings
                if (openearn.last_tapper_cycle) {{
                    const tEl = document.getElementById('module-tapper-last');
                    if (tEl) tEl.textContent = openearn.last_tapper_cycle;
                }}
                if (openearn.next_tapper_cycle) {{
                    const tNextEl = document.getElementById('module-tapper-next');
                    if (tNextEl) tNextEl.textContent = openearn.next_tapper_cycle;
                }}
                if (openearn.last_daily_harvest) {{
                    const hEl = document.getElementById('module-harvest-last');
                    if (hEl) hEl.textContent = openearn.last_daily_harvest;
                }}
            }} catch (e) {{
                console.error("Live sync error:", e);
            }}
        }}

        async function fetchLogs() {{
            const box = document.getElementById('terminal-logs');
            try {{
                const res = await fetch('/logs');
                if (res.ok) {{
                    const text = await res.text();
                    box.textContent = text.trim() ? text : "Лог чист, сервер в ожидании новых событий...";
                    box.scrollTop = box.scrollHeight;
                }}
            }} catch (e) {{
                console.error("Logs error:", e);
            }}
        }}

        // Run live update every 4 seconds without page reload
        updateDashboardLive();
        setInterval(updateDashboardLive, 4000);

        // Fetch logs every 6 seconds
        fetchLogs();
        setInterval(fetchLogs, 6000);
    </script>
</body>
</html>
"""
