import json
import os

with open('database.json', encoding='utf-8') as f:
    db = json.load(f)

paco_sessions = {os.path.splitext(f)[0] for f in os.listdir('sessions') if f.endswith('.session')}
rb_dir = r'C:\Users\hoaki\Desktop\RB_Autimatic\sessions'
rb_sessions = {os.path.splitext(f)[0] for f in os.listdir(rb_dir) if f.endswith('.session')} if os.path.exists(rb_dir) else set()
all_sessions = paco_sessions | rb_sessions

targets = []

for parent_name, data in db.items():
    if data.get('status') == 'DEAD' or data.get('withdrawn', False):
        continue
    avail = data.get('available', 0.0)
    held = data.get('held', 0.0)
    children = data.get('children', [])
    
    # Check alive children
    alive_children = [c for c in children if c in all_sessions]
    
    if alive_children:
        targets.append({
            'parent': parent_name,
            'avail': avail,
            'held': held,
            'status': data.get('status'),
            'alive_children': alive_children
        })

print(f"Total parent targets with alive children: {len(targets)}")
# Sort by avail descending
targets.sort(key=lambda x: (x['avail'], len(x['alive_children'])), reverse=True)

with open('targets_report.json', 'w', encoding='utf-8') as f:
    json.dump(targets, f, indent=2, ensure_ascii=False)

for t in targets[:25]:
    p = t['parent']
    av = t['avail']
    hd = t['held']
    ac = len(t['alive_children'])
    print(f"Parent: {p[:30]:<30} | Avail: ${av:.2f} | Held: ${hd:.2f} | Alive children: {ac}")
