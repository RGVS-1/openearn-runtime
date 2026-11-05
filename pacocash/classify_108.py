import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

RB_DIR = r"C:\Users\hoaki\Desktop\RB_Autimatic"
SESSIONS_DIR = os.path.join(RB_DIR, "sessions")

# 1. Load the 108 accounts
sessions = sorted([
    f[:-8] for f in os.listdir(SESSIONS_DIR)
    if f.endswith('.session') and not f.startswith('temp_regen')
])

print(f"Total target accounts: {len(sessions)}")

# 2. Load withdrawals
w_file = r"c:\Users\hoaki\Desktop\Pacocash\withdrawals.json"
withdrawals_list = json.load(open(w_file, encoding='utf-8')) if os.path.exists(w_file) else []
withdrawn_map = {}
for w in withdrawals_list:
    if isinstance(w, dict) and 'account' in w:
        withdrawn_map[w['account']] = w

# 3. Load database.json
db_file = r"c:\Users\hoaki\Desktop\Pacocash\database.json"
db = json.load(open(db_file, encoding='utf-8')) if os.path.exists(db_file) else {}

# 4. Load wallets.json
wallets_file = r"c:\Users\hoaki\Desktop\Pacocash\wallets.json"
wallets = json.load(open(wallets_file, encoding='utf-8')) if os.path.exists(wallets_file) else {}

# Classify accounts
group_withdrawn = []       # Участвовали и получили выплату
group_participated_no_payout = [] # Участвовали, но выплату НЕ получили
group_never_participated = []     # Вообще НЕ участвовали в PacoCash

for acc in sessions:
    has_withdrawn = acc in withdrawn_map
    in_db = acc in db
    in_wallets = acc in wallets

    if has_withdrawn:
        w_info = withdrawn_map[acc]
        group_withdrawn.append({
            "name": acc,
            "amount": w_info.get("amount", 0.0),
            "date": w_info.get("timestamp", ""),
            "status": w_info.get("status", "CLAIMED")
        })
    elif in_db or in_wallets:
        db_info = db.get(acc, {})
        group_participated_no_payout.append({
            "name": acc,
            "status": db_info.get("status", "UNKNOWN"),
            "available": db_info.get("available", 0.0),
            "held": db_info.get("held", 0.0),
            "pending_ref": db_info.get("pending_ref", 0.0),
            "referrals_count": db_info.get("referrals_count", 0),
            "parent_ref": db_info.get("parent_ref", "")
        })
    else:
        group_never_participated.append(acc)

print(f"\n1. Получили выплату: {len(group_withdrawn)}")
print(f"2. Участвовали, но НЕ получили выплату: {len(group_participated_no_payout)}")
print(f"3. Вообще НЕ участвовали: {len(group_never_participated)}")

total_classified = len(group_withdrawn) + len(group_participated_no_payout) + len(group_never_participated)
print(f"Total check: {total_classified} == {len(sessions)}")

# Let's save a structured json
result = {
    "total_accounts": len(sessions),
    "withdrawn": group_withdrawn,
    "participated_no_payout": group_participated_no_payout,
    "never_participated": group_never_participated
}

with open(r"c:\Users\hoaki\Desktop\Pacocash\audit_108_paco_status.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print("\n--- Details of never participated ---")
for x in group_never_participated:
    print(f"  - {x}")

print("\n--- Summary of participated without payout ---")
avail_ge_1 = [x for x in group_participated_no_payout if x['available'] >= 1.0]
avail_05 = [x for x in group_participated_no_payout if 0.4 <= x['available'] < 1.0]
avail_0 = [x for x in group_participated_no_payout if x['available'] < 0.4]

print(f"  >= $1.00 (готовы или были готовы к выводу): {len(avail_ge_1)}")
print(f"  $0.50 (застряли на минималке из-за 51 смс/рефералов): {len(avail_05)}")
print(f"  $0.00 / листовые / нулевые: {len(avail_0)}")
