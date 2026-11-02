# HTML Dashboard Template for TheOpenEarn + Pixelmania & Promo Sniper

def render_dashboard_html(stats: dict) -> str:
    openearn = stats.get("openearn_stats", {})
    pixelmania = stats.get("pixelmania_stats", {})
    sniper = stats.get("promo_sniper", {})
    
    tot = openearn.get("total_farm_tot", 0)
    stars = openearn.get("total_farm_stars", 0.0)
    accs_count = openearn.get("accounts_total", 110)
    last_tapper = openearn.get("last_tapper_cycle") or "Ожидание цикла..."
    last_harvest = openearn.get("last_daily_harvest") or "Сегодня ещё не выполнялся"
    
    pm_status = pixelmania.get("status", "IDLE")
    pm_accs = pixelmania.get("accounts_count", 109)
    pm_mined = pixelmania.get("total_pixels_mined", 0)
    pm_winners = pixelmania.get("golden_winners_count", 0)
    pm_last = pixelmania.get("last_run") or "Ожидание запуска..."
    
    promos_count = sniper.get("intercepted_promos_count", 0)
    recent_activations = sniper.get("recent_activations", [])
    
    # Format activation table rows
    rows_html = ""
    if not recent_activations:
        rows_html = """
        <tr>
            <td colspan="5" class="py-6 text-center text-slate-500 italic">
                <i class="fa-solid fa-radar mr-2 text-indigo-400"></i> Снайпер в активном режиме ожидания. При появлении нового поста в @lh_promocodes здесь появится результат перехвата.
            </td>
        </tr>
        """
    else:
        for act in reversed(recent_activations):
            time_str = act.get("timestamp", "-")
            target = act.get("target", {})
            platform = target.get("platform", "Unknown")
            voucher = target.get("voucher") or target.get("start_param") or target.get("url", "-")
            succ = act.get("success_count", 0)
            total = act.get("total_accounts", 110)
            reasons = act.get("reasons", {})
            
            # Badge
            if succ > 0:
                badge = f'<span class="bg-emerald-500/20 text-emerald-400 px-2.5 py-1 rounded-full text-xs font-semibold border border-emerald-500/30"><i class="fa-solid fa-circle-check mr-1"></i>Успешно: {succ}/{total}</span>'
            else:
                badge = f'<span class="bg-amber-500/20 text-amber-400 px-2.5 py-1 rounded-full text-xs font-semibold border border-amber-500/30"><i class="fa-solid fa-circle-exclamation mr-1"></i>Не активирован (0/{total})</span>'
            
            # Format reasons breakdown
            reasons_desc = []
            for r_key, r_cnt in reasons.items():
                if "exhausted" in r_key.lower() or "исчерпан" in r_key.lower():
                    reasons_desc.append(f'<span class="text-amber-300">Чек исчерпан другими ({r_cnt} акк.)</span>')
                elif "User not registered" in r_key:
                    reasons_desc.append(f'<span class="text-red-400">Не зарегистрирован в боте ({r_cnt} акк.)</span>')
                elif "unauthorized" in r_key:
                    reasons_desc.append(f'<span class="text-rose-400">Сессия заморожена ({r_cnt} акк.)</span>')
                else:
                    reasons_desc.append(f'<span class="text-slate-400">{r_key} ({r_cnt} акк.)</span>')
            
            reasons_str = "<br>".join(reasons_desc) if reasons_desc else '<span class="text-slate-500">-</span>'
            
            rows_html += f"""
            <tr class="border-b border-slate-800/80 hover:bg-slate-800/30 transition-colors">
                <td class="py-3 px-4 font-mono text-xs text-slate-400">{time_str}</td>
                <td class="py-3 px-4"><span class="bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded text-xs font-bold uppercase">{platform}</span></td>
                <td class="py-3 px-4 font-mono text-xs text-amber-200 select-all">{voucher}</td>
                <td class="py-3 px-4">{badge}</td>
                <td class="py-3 px-4 text-xs">{reasons_str}</td>
            </tr>
            """

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenEarn & Pixelmania Control Center</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        body {{
            font-family: 'Plus Jakarta Sans', sans-serif;
            background: #090d16;
        }}
        .font-mono {{
            font-family: 'JetBrains Mono', monospace;
        }}
        .glass-card {{
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .glass-card:hover {{
            border-color: rgba(99, 102, 241, 0.3);
        }}
        .pulse-dot {{
            box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            animation: pulse-green 2s infinite;
        }}
        @keyframes pulse-green {{
            0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
            70% {{ box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}
    </style>
</head>
<body class="text-slate-100 min-h-screen pb-12">
    <!-- Navbar -->
    <header class="border-b border-slate-800/80 bg-slate-900/60 sticky top-0 z-50 backdrop-blur-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                    <i class="fa-solid fa-server text-white text-lg"></i>
                </div>
                <div>
                    <h1 class="font-bold text-lg leading-tight flex items-center gap-2">
                        Cloud Farm & Sniper
                        <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Render 24/7</span>
                    </h1>
                    <p class="text-xs text-slate-400">TheOpenEarn • Pixelmania • @lh_promocodes</p>
                </div>
            </div>

            <div class="flex items-center gap-3">
                <div class="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 pulse-dot"></span>
                    <span>ONLINE 24/7 (Frankfurt)</span>
                </div>
                <button onclick="window.location.reload()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition flex items-center gap-1.5 shadow-sm">
                    <i class="fa-solid fa-rotate text-slate-400"></i> Обновить
                </button>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6 space-y-6">
        <!-- Top Metrics Cards -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <!-- Card 1: TOT Balance -->
            <div class="glass-card rounded-2xl p-5 relative overflow-hidden group">
                <div class="absolute -right-4 -bottom-4 w-24 h-24 bg-cyan-500/10 rounded-full blur-xl group-hover:bg-cyan-500/20 transition-all"></div>
                <div class="flex items-center justify-between text-slate-400 text-xs font-medium uppercase tracking-wider">
                    <span>TheOpenEarn TOT</span>
                    <i class="fa-solid fa-coins text-cyan-400 text-base"></i>
                </div>
                <div class="mt-3 flex items-baseline gap-2">
                    <span class="text-3xl font-extrabold text-white tracking-tight">{tot:,}</span>
                    <span class="text-xs font-semibold text-cyan-400">TOT</span>
                </div>
                <div class="mt-2 text-xs text-slate-400 flex items-center gap-1.5">
                    <span class="text-emerald-400 font-semibold"><i class="fa-solid fa-bolt mr-1"></i>Тапалка активна</span>
                    <span>(каждые 5 мин)</span>
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
                    <span class="text-3xl font-extrabold text-amber-300 tracking-tight">{stars:.4f}</span>
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
                    <span class="text-3xl font-extrabold text-purple-200 tracking-tight">{pm_mined}</span>
                    <span class="text-xs font-semibold text-purple-400">вскопано</span>
                </div>
                <div class="mt-2 text-xs text-slate-400 flex items-center justify-between">
                    <span>Золотых призов: <strong class="text-amber-300 font-bold">{pm_winners}</strong></span>
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
                    <span class="text-3xl font-extrabold text-emerald-300 tracking-tight">{promos_count}</span>
                    <span class="text-xs font-semibold text-slate-400">перехватов</span>
                </div>
                <div class="mt-2 text-xs text-emerald-400 font-semibold flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 pulse-dot"></span>
                    <span>MTProto + 3s Backup Poller</span>
                </div>
            </div>
        </div>

        <!-- Section: Promo Sniper Live Feed -->
        <div class="glass-card rounded-2xl overflow-hidden shadow-xl">
            <div class="p-5 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-4">
                <div>
                    <h2 class="text-base font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-bolt text-amber-400"></i> Журнал перехвата промокодов & ваучеров
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
                            <th class="py-3 px-4">Время</th>
                            <th class="py-3 px-4">Бот / Платформа</th>
                            <th class="py-3 px-4">Код / Ваучер</th>
                            <th class="py-3 px-4">Статус активации</th>
                            <th class="py-3 px-4">Подробности & Ошибки</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Modules Status Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- OpenEarn Module -->
            <div class="glass-card rounded-2xl p-5 space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                    <h3 class="font-bold text-base flex items-center gap-2 text-white">
                        <i class="fa-solid fa-gamepad text-cyan-400"></i> TheOpenEarn Авто-ферма
                    </h3>
                    <span class="text-xs font-semibold px-2.5 py-1 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                        110 аккаунтов
                    </span>
                </div>

                <div class="space-y-3 text-xs">
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Последний круг тапалки (5 мин):</span>
                        <span class="font-mono text-slate-200">{last_tapper}</span>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Ежедневный сбор наград:</span>
                        <span class="font-mono text-slate-200">{last_harvest}</span>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Энергия за цикл:</span>
                        <span class="text-emerald-400 font-semibold">+100 TOT / акк (~11,000 TOT на ферму)</span>
                    </div>
                </div>

                <div class="pt-2 flex items-center gap-3">
                    <button onclick="triggerAction('/harvest', this)" class="w-full py-2.5 px-4 bg-cyan-600 hover:bg-cyan-500 active:scale-[0.98] text-white font-semibold rounded-xl text-xs transition shadow-lg shadow-cyan-600/20 flex items-center justify-center gap-2">
                        <i class="fa-solid fa-hand-holding-dollar"></i> Собрать чекин и кейсы прямо сейчас
                    </button>
                </div>
            </div>

            <!-- Pixelmania Module -->
            <div class="glass-card rounded-2xl p-5 space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                    <h3 class="font-bold text-base flex items-center gap-2 text-white">
                        <i class="fa-solid fa-wand-magic-sparkles text-purple-400"></i> Pixelmania 10M Карта
                    </h3>
                    <span class="text-xs font-semibold px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20">
                        Статус: {pm_status}
                    </span>
                </div>

                <div class="space-y-3 text-xs">
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Всего вскопано пикселей:</span>
                        <span class="font-mono text-purple-300 font-bold">{pm_mined} точек</span>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Найденные золотые пиксели / призы:</span>
                        <span class="font-mono text-amber-300 font-bold">{pm_winners}</span>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Последний запуск:</span>
                        <span class="font-mono text-slate-200">{pm_last}</span>
                    </div>
                </div>

                <div class="pt-2 flex items-center gap-3">
                    <button onclick="triggerAction('/pixelmania/run', this)" class="w-full py-2.5 px-4 bg-purple-600 hover:bg-purple-500 active:scale-[0.98] text-white font-semibold rounded-xl text-xs transition shadow-lg shadow-purple-600/20 flex items-center justify-center gap-2">
                        <i class="fa-solid fa-hammer"></i> Запустить копку пикселей и дейлик сейчас
                    </button>
                </div>
            </div>
        </div>

        <!-- Terminal Logs Window -->
        <div class="glass-card rounded-2xl overflow-hidden shadow-xl">
            <div class="p-4 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="w-3 h-3 rounded-full bg-rose-500/80 inline-block"></span>
                    <span class="w-3 h-3 rounded-full bg-amber-500/80 inline-block"></span>
                    <span class="w-3 h-3 rounded-full bg-emerald-500/80 inline-block"></span>
                    <span class="ml-2 font-mono text-xs text-slate-400">Живой консольный лог сервера (Render Cloud)</span>
                </div>
                <button onclick="fetchLogs()" class="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-mono">
                    <i class="fa-solid fa-arrows-rotate"></i> Обновить лог
                </button>
            </div>
            <div id="terminal-logs" class="p-4 bg-slate-950 font-mono text-xs text-slate-300 h-64 overflow-y-auto whitespace-pre-wrap leading-relaxed select-text">
Загрузка логов с сервера...
            </div>
        </div>
    </main>

    <footer class="mt-8 text-center text-xs text-slate-600">
        Автономный облачный комбайн • Пинг cron-job.org каждые 5 мин • Сервер работает 24/7
    </footer>

    <script>
        async function fetchLogs() {{
            const box = document.getElementById('terminal-logs');
            try {{
                const res = await fetch('/logs');
                if (res.ok) {{
                    const text = await res.text();
                    box.textContent = text.trim() ? text : "Лог чист, сервер в ожидании новых событий...";
                    box.scrollTop = box.scrollHeight;
                }} else {{
                    box.textContent = "Ошибка получения логов: " + res.status;
                }}
            }} catch (e) {{
                box.textContent = "Сетевая ошибка при загрузке логов: " + e;
            }}
        }}

        async function triggerAction(endpoint, btn) {{
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Запуск в фоне...';
            try {{
                const res = await fetch(endpoint);
                const data = await res.json();
                btn.innerHTML = '<i class="fa-solid fa-check text-emerald-300"></i> Запущено!';
                setTimeout(() => {{
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                    window.location.reload();
                }}, 2000);
            }} catch (e) {{
                btn.innerHTML = '<i class="fa-solid fa-xmark text-rose-300"></i> Ошибка запуска';
                setTimeout(() => {{
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                }}, 2500);
            }}
        }}

        // Auto fetch logs on load and auto refresh page every 15s
        fetchLogs();
        setInterval(fetchLogs, 8000);
        setTimeout(() => {{ window.location.reload(); }}, 15000);
    </script>
</body>
</html>"""
