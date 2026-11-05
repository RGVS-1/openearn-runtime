import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

data = json.load(open(r'c:\Users\hoaki\Desktop\Pacocash\audit_108_paco_status.json', encoding='utf-8'))

print('=== 1. ПОЛУЧИЛИ ВЫПЛАТУ (28 шт) ===')
total_payout = 0.0
for i, x in enumerate(data['withdrawn']):
    total_payout += x['amount']
    print(f"{i+1:2d}. {x['name']} | Выведено: ${x['amount']:.2f} | Дата: {x['date'][:10]}")
print(f"Итого выведено с этих 28 аккаунтов: ${total_payout:.2f} USDT")

print('\n=== 2. УЧАСТВОВАЛИ, НО БЕЗ ВЫПЛАТЫ (53 шт) ===')
for i, x in enumerate(data['participated_no_payout']):
    print(f"{i+1:2d}. {x['name']} | Баланс: ${x['available']:.2f} (в холде: ${x['held']:.2f}) | Рефов: {x['referrals_count']} | Статус: {x['status']}")

print('\n=== 3. ВООБЩЕ НЕ УЧАСТВОВАЛИ В PACOCASH (27 шт) ===')
for i, x in enumerate(data['never_participated']):
    print(f"{i+1:2d}. {x}")
