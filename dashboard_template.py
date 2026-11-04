# HTML Dashboard Template for TheOpenEarn + Pixelmania & Promo Sniper & CasinoCG & JVault

def render_dashboard_html(stats: dict) -> str:
    openearn = stats.get("openearn_stats", {})
    pixelmania = stats.get("pixelmania_stats", {})
    sniper = stats.get("promo_sniper", {})
    
    tot = openearn.get("total_farm_tot", 0)
    stars = openearn.get("total_farm_stars", 0.0)
    accs_count = openearn.get("accounts_total", 110)
    last_tapper = openearn.get("last_tapper_cycle") or "В процессе..."
    last_harvest = openearn.get("last_daily_harvest") or "Авто-сбор активен"
    
    pm_status = pixelmania.get("status", "IDLE")
    pm_accs = pixelmania.get("accounts_count", 109)
    pm_mined = pixelmania.get("total_pixels_mined", 0)
    pm_winners = pixelmania.get("golden_winners_count", 0)
    pm_last = pixelmania.get("last_run") or "В процессе..."
    
    promos_count = sniper.get("intercepted_promos_count", 0)
    recent_activations = sniper.get("recent_activations", [])
    
    cg = stats.get("casinocg_flywheel", {})
    cg_cycle = cg.get("cycle_count", 2)
    cg_scale = cg.get("current_scale", 1)
    cg_withdrawn = float(cg.get("total_withdrawn_usd", 0.0))
    cg_cheques_count = cg.get("total_cheques_collected", 0)
    cg_actual_withdrawn = cg_withdrawn if cg_cheques_count > 0 else 0.0
    pending_list = cg.get("pending_withdrawals", [])
    cg_pending_count = len(pending_list)
    cg_sold_count = len(cg.get("sold_accounts", []))
    
    # Format withdrawal items
    withdrawals_html = ""
    if not pending_list:
        withdrawals_html = '<tr><td colspan="5" class="py-3 px-4 text-center text-slate-500 italic">Нет активных заявок</td></tr>'
    else:
        for pw in pending_list:
            rid = pw.get("request_id")
            amt = float(pw.get("amount", 0.0))
            phone = pw.get("phone", "-")
            status = pw.get("status", "pending")
            time_created = pw.get("created_at", "-")
            if rid in [376, 377]:
                badge = '<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30"><i class="fa-solid fa-xmark mr-1"></i>Отклонено (твинк/мульт)</span>'
            elif status == "pending":
                badge = '<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30"><i class="fa-solid fa-clock mr-1"></i>На модерации (xRocket)</span>'
            else:
                badge = f'<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">{status}</span>'
            
            withdrawals_html += f"""
            <tr class="border-b border-slate-800/60 hover:bg-slate-800/20 transition-colors">
                <td class="py-2.5 px-4 font-mono text-xs text-amber-300 font-bold">#{rid}</td>
                <td class="py-2.5 px-4 font-mono text-xs text-slate-300">{phone}</td>
                <td class="py-2.5 px-4 font-bold text-xs text-emerald-400">${amt:.2f} USDT</td>
                <td class="py-2.5 px-4 text-xs text-slate-400"><span class="bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded text-xs font-semibold">xRocket</span></td>
                <td class="py-2.5 px-4">{badge}</td>
            </tr>
            """

    jv = stats.get("jvault_miner", {})
    jv_accounts = jv.get("total_accounts", 110)
    jv_assets = float(jv.get("total_assets_jvt", 0.0))
    jv_holding = float(jv.get("total_holding_jvt", 0.0))
    jv_usd = float(jv.get("total_usd_value", jv_assets * 0.0252))
    jv_master = float(jv.get("master_assets", 98.53))
    jv_master_pct = min(100.0, round((jv_master / 250.0) * 100, 1))
    jv_status = jv.get("status", "ACTIVE")
    
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
            voucher = target.get("code") or target.get("voucher") or target.get("start_param") or target.get("url", "-")
            succ = act.get("success_count", 0)
            total = act.get("total_accounts", 110)
            reasons = act.get("reasons", {})
            
            # Badge
            if succ > 0:
                reward_note = act.get("reward_summary", "")
                badge = f'<span class="bg-emerald-500/20 text-emerald-400 px-2.5 py-1 rounded-full text-xs font-semibold border border-emerald-500/30"><i class="fa-solid fa-circle-check mr-1"></i>Успешно: {succ}/{total}</span>'
            else:
                badge = f'<span class="bg-amber-500/20 text-amber-400 px-2.5 py-1 rounded-full text-xs font-semibold border border-amber-500/30"><i class="fa-solid fa-circle-exclamation mr-1"></i>Не активирован (0/{total})</span>'
            
            # Format reasons breakdown
            reasons_desc = []
            if succ > 0 and act.get("reward_summary"):
                reasons_desc.append(f'<span class="text-emerald-300 font-bold"><i class="fa-solid fa-gift mr-1"></i>{act.get("reward_summary")}</span>')

            for r_key, r_cnt in reasons.items():
                if "exhausted" in r_key.lower() or "исчерпан" in r_key.lower() or "закончился" in r_key.lower() or "лимит" in r_key.lower():
                    reasons_desc.append(f'<span class="text-amber-300">Исчерпан другими / Закончился ({r_cnt} акк.)</span>')
                elif "депозит" in r_key.lower() or "deposit" in r_key.lower():
                    reasons_desc.append(f'<span class="text-amber-300">Требуется депозит GRAM ({r_cnt} акк.)</span>')
                elif "24 ч" in r_key.lower() or "after_24h" in r_key.lower() or "24h" in r_key.lower():
                    reasons_desc.append(f'<span class="text-amber-300">Доступен через 24 ч после входа ({r_cnt} акк.)</span>')
                elif "уже активирован" in r_key.lower() or "already_activated" in r_key.lower():
                    reasons_desc.append(f'<span class="text-cyan-400">Уже активирован ранее ({r_cnt} акк.)</span>')
                elif "капч" in r_key.lower() or "captcha" in r_key.lower():
                    reasons_desc.append(f'<span class="text-purple-300">Капча не решена ({r_cnt} акк.)</span>')
                elif "User not registered" in r_key:
                    reasons_desc.append(f'<span class="text-red-400">Не зарегистрирован в боте ({r_cnt} акк.)</span>')
                elif "unauthorized" in r_key:
                    reasons_desc.append(f'<span class="text-rose-400">Сессия заморожена ({r_cnt} акк.)</span>')
                elif "unhandled platform" in r_key:
                    reasons_desc.append(f'<span class="text-slate-400">Платформа в разработке ({r_cnt} акк.)</span>')
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
<html lang="ru" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cloud Farm & Sniper Hub | 24/7 Render Dashboard</title>
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
        <!-- Header -->
        <header class="flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-slate-800">
            <div class="flex items-center gap-3">
                <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                    <i class="fa-solid fa-server text-white text-xl"></i>
                </div>
                <div>
                    <h1 class="text-xl sm:text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
                        Cloud Farm & Sniper
                        <span class="text-xs font-bold px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">Render 24/7</span>
                    </h1>
                    <p class="text-xs text-slate-400 font-medium mt-0.5">TheOpenEarn • Pixelmania • JVault Miner • @lh_promocodes</p>
                </div>
            </div>
            
            <div class="flex items-center gap-3">
                <div class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-emerald-400">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 pulse-dot"></span>
                    <span>ONLINE 24/7 (Frankfurt)</span>
                </div>
                <div class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-slate-400">
                    <i class="fa-solid fa-clock-rotate-left text-indigo-400"></i>
                    <span>Live Sync <span id="sync-indicator">0s</span></span>
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

        <!-- Modules Status Grid (TheOpenEarn & Pixelmania) -->
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
                        <span id="stat-tapper-cycle" class="font-mono text-slate-200">{last_tapper}</span>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Ежедневный сбор наград:</span>
                        <span id="stat-harvest-cycle" class="font-mono text-slate-200">{last_harvest}</span>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Энергия за цикл:</span>
                        <span class="text-emerald-400 font-semibold">+100 TOT / акк (~11,000 TOT на ферму)</span>
                    </div>
                </div>

                <div class="pt-2">
                    <div class="flex items-center justify-between text-xs text-slate-400 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                        <div class="flex items-center gap-2">
                            <span class="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse"></span>
                            <span class="text-cyan-300 font-semibold">Непрерывный авто-фарм 24/7 активен</span>
                        </div>
                        <span class="text-slate-500 font-mono">Тапалка (5 мин) + дейлик-кейс</span>
                    </div>
                </div>
            </div>

            <!-- Pixelmania Module -->
            <div class="glass-card rounded-2xl p-5 space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                    <h3 class="font-bold text-base flex items-center gap-2 text-white">
                        <i class="fa-solid fa-wand-magic-sparkles text-purple-400"></i> Pixelmania 10M Карта
                    </h3>
                    <span id="stat-pm-status" class="text-xs font-semibold px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20">
                        Статус: {pm_status}
                    </span>
                </div>

                <div class="space-y-3 text-xs">
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Всего вскопано пикселей:</span>
                        <span id="stat-pm-mined" class="font-mono text-purple-300 font-bold">{pm_mined} точек</span>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Найденные золотые пиксели / призы:</span>
                        <span id="stat-pm-winners" class="font-mono text-amber-300 font-bold">{pm_winners}</span>
                    </div>
                    <div class="flex items-center justify-between py-2 border-b border-slate-800/50">
                        <span class="text-slate-400">Последний запуск:</span>
                        <span id="stat-pm-last" class="font-mono text-slate-200">{pm_last}</span>
                    </div>
                </div>

                <div class="pt-2">
                    <div class="flex items-center justify-between text-xs text-slate-400 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                        <div class="flex items-center gap-2">
                            <span class="w-2.5 h-2.5 rounded-full bg-purple-400 animate-pulse"></span>
                            <span class="text-purple-300 font-semibold">Автономная копка карты 24/7 активна</span>
                        </div>
                        <span class="text-slate-500 font-mono">10M карта + дейлик + задания</span>
                    </div>
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
    </div>

    <footer class="mt-8 text-center text-xs text-slate-600">
        Автономный облачный комбайн • Пинг cron-job.org каждые 5 мин • Сервер работает 24/7
    </footer>

    <script>
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

                // Update TOT & Stars with smooth number formatting
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
                const elPmMined = document.getElementById('stat-pm-mined');
                if (elPmMined && pixelmania.total_pixels_mined !== undefined) {{
                    elPmMined.textContent = Number(pixelmania.total_pixels_mined).toLocaleString() + ' точек';
                }}
                const elWinners = document.getElementById('stat-winners');
                if (elWinners && pixelmania.golden_winners_count !== undefined) {{
                    elWinners.textContent = pixelmania.golden_winners_count;
                }}
                const elPmWinners = document.getElementById('stat-pm-winners');
                if (elPmWinners && pixelmania.golden_winners_count !== undefined) {{
                    elPmWinners.textContent = pixelmania.golden_winners_count;
                }}
                const elPmStatus = document.getElementById('stat-pm-status');
                if (elPmStatus && pixelmania.status) {{
                    elPmStatus.textContent = 'Статус: ' + pixelmania.status;
                }}
                const elPmLast = document.getElementById('stat-pm-last');
                if (elPmLast && pixelmania.last_run) {{
                    elPmLast.textContent = pixelmania.last_run;
                }}

                // Update Cycles
                const elTapper = document.getElementById('stat-tapper-cycle');
                if (elTapper && openearn.last_tapper_cycle) {{
                    elTapper.textContent = openearn.last_tapper_cycle;
                }}
                const elHarvest = document.getElementById('stat-harvest-cycle');
                if (elHarvest && openearn.last_daily_harvest) {{
                    elHarvest.textContent = openearn.last_daily_harvest;
                }}

                // Update Promos
                const elPromos = document.getElementById('stat-promos-count');
                if (elPromos && sniper.intercepted_promos_count !== undefined) {{
                    elPromos.textContent = sniper.intercepted_promos_count;
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

        // Run live update every 3.5 seconds without page reload
        updateDashboardLive();
        setInterval(updateDashboardLive, 3500);

        // Fetch logs every 6 seconds
        fetchLogs();
        setInterval(fetchLogs, 6000);
    </script>
</body>
</html>