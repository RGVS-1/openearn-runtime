import json
import sys
from datetime import datetime, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

db = json.load(open('database.json', encoding='utf-8'))
parents = {k: v for k, v in db.items() if v.get('children') and not v.get('withdrawn')}

print(f'Total pending parent accounts: {len(parents)}')

schedule = []
for p, p_data in parents.items():
    children = p_data.get('children', [])
    c_times = []
    for c in children:
        c_data = db.get(c, {})
        c_done = c_data.get('completed_at')
        if c_done:
            try:
                c_dt = datetime.fromisoformat(c_done)
                c_times.append(c_dt)
            except Exception:
                pass
    if c_times:
        latest_c = max(c_times)
        unlock_time = latest_c + timedelta(days=2)
        schedule.append((unlock_time, p, len(children), [c.strftime('%d.%m %H:%M') for c in c_times]))

schedule.sort(key=lambda x: x[0])

now = datetime.now()
print('\n--- UPCOMING UNLOCK SCHEDULE ---')
for u_time, p, count, c_strs in schedule:
    diff = u_time - now
    sec = diff.total_seconds()
    if sec < 0:
        d_str = f'ГОТОВО К РАЗБЛОКИРОВКЕ (прошло {-sec/60:.0f} мин назад)'
    else:
        d_str = f'через {sec/3600:.1f} ч ({sec/60:.0f} мин)'
    print(f"{u_time.strftime('%d.%m %H:%M')} | {d_str} | {p}")
