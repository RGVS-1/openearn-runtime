import json
import os
import sys

with open('database.json', encoding='utf-8') as f:
    db = json.load(f)

# check sessions in Pacocash/sessions
paco_sessions = {os.path.splitext(f)[0] for f in os.listdir('sessions') if f.endswith('.session')}

# check sessions in RB_Autimatic/sessions
rb_dir = r'C:\Users\hoaki\Desktop\RB_Autimatic\sessions'
rb_sessions = {os.path.splitext(f)[0] for f in os.listdir(rb_dir) if f.endswith('.session')} if os.path.exists(rb_dir) else set()

# check sessions in TG_farm
tg_dir = r'C:\Users\hoaki\Desktop\TG_farm'
tg_sessions = set()
if os.path.exists(tg_dir):
    for root, dirs, files in os.walk(tg_dir):
        for f in files:
            if f.endswith('.session'):
                tg_sessions.add(os.path.splitext(f)[0])

print(f'Paco sessions: {len(paco_sessions)}')
print(f'RB sessions: {len(rb_sessions)}')
print(f'TG_farm sessions: {len(tg_sessions)}')

parents_with_children = []
for name, data in db.items():
    children = data.get('children', [])
    avail = data.get('available', 0.0)
    held = data.get('held', 0.0)
    if children and not data.get('withdrawn', False) and data.get('status') != 'DEAD':
        child_status = []
        for ch in children:
            has_paco = ch in paco_sessions
            has_rb = ch in rb_sessions
            has_tg = ch in tg_sessions
            child_status.append((ch, has_paco, has_rb or has_tg))
        parents_with_children.append((name, avail, held, child_status))

print(f'\nTotal non-withdrawn parents with children: {len(parents_with_children)}')
total_potential_boost = 0
for p, avail, held, ch_list in parents_with_children:
    alive_children = [c for c, in_paco, in_other in ch_list if in_paco or in_other]
    print(f"Parent: {p.encode('ascii', 'replace').decode()} | Avail: {avail} | Held: {held} | Children total: {len(ch_list)} (alive sessions: {len(alive_children)})")
    if avail + len(alive_children) * 0.5 >= 1.0:
        total_potential_boost += 1

print(f"\nParents that CAN reach >= $1.00 if children qualify: {total_potential_boost}")
