import asyncio
import json
import logging
import os
import sys
import time
import urllib.parse
import requests
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.messages import RequestWebViewRequest

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

logger = logging.getLogger("jvault_miner")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

MASTER_REF = "8224259468"  # Xxxcalibur's referral code
MASTER_WALLET = "UQCsilFQ1DZeU7WxQyHtZbXV1E_60Gq8sp7a8aI48yOVHGWq"
STATE_FILE = "jvault_accounts_state.json"
SUMMARY_FILE = "jvault_summary.json"
WALLETS_FILE = "ton_wallets.json"

def load_wallets():
    if os.path.exists(WALLETS_FILE):
        try:
            with open(WALLETS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_wallets(wallets):
    try:
        with open(WALLETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(wallets, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save wallets: {e}")

def get_or_create_wallet_for_account(acc_name):
    wallets = load_wallets()
    master_key = '[RU] Xxxcalibur +79936124946 2025'
    if acc_name == master_key:
        return MASTER_WALLET
    if acc_name in wallets and wallets[acc_name].get('address') != MASTER_WALLET:
        return wallets[acc_name]['address']
    
    # Generate new unique wallet
    from tonsdk.contract.wallet import Wallets, WalletVersionEnum
    from tonsdk.crypto import mnemonic_new
    mnemonics = mnemonic_new()
    _, _, _, wallet = Wallets.create(version=WalletVersionEnum.v4r2, workchain=0, mnemonics=mnemonics)
    addr = wallet.address.to_string(True, True, False)
    wallets[acc_name] = {"address": addr, "mnemonics": mnemonics, "created_at": time.time()}
    save_wallets(wallets)
    return addr

def get_proxy_dicts(meta):
    t_px = meta['proxy']['telethon']
    u, p, h, pt = t_px['username'], t_px['password'], t_px['addr'], t_px['port']
    http_px = f'http://{u}:{p}@{h}:{pt}'
    return t_px, {'http': http_px, 'https': http_px}

def load_summary():
    if os.path.exists(SUMMARY_FILE):
        try:
            with open(SUMMARY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "total_accounts": 0,
        "total_assets_jvt": 0.0,
        "total_holding_jvt": 0.0,
        "total_usd_value": 0.0,
        "master_assets": 0.0,
        "master_invites": 0,
        "ready_for_withdraw": 0,
        "last_run": None,
        "status": "IDLE"
    }

def save_summary(summary):
    try:
        with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save summary: {e}")

async def run_jvault_single(acc_name, meta, cfg):
    t_px, proxies = get_proxy_dicts(meta)
    client = TelegramClient(f'sessions/{acc_name}.session', cfg['api_id'], cfg['api_hash'], proxy=t_px, connection_retries=1, **meta['device'])
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning(f"[{acc_name}] Session unauthorized.")
            return {"success": False, "error": "Unauthorized"}

        bot = await client.get_entity('JVaultMinerBot')
        res = await client(RequestWebViewRequest(
            peer=bot,
            bot=bot,
            url='https://jvaultminer.world/',
            start_param=MASTER_REF,
            platform='android'
        ))
        await client.disconnect()
    except Exception as e:
        logger.error(f"[{acc_name}] Telethon webview error: {e}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return {"success": False, "error": str(e)}

    # Parse WebApp initData
    frag = urllib.parse.urlparse(res.url).fragment
    qs = urllib.parse.parse_qs(frag)
    init_data = qs.get('tgWebAppData', [''])[0]
    if not init_data:
        return {"success": False, "error": "Empty initData"}

    user_obj = json.loads(urllib.parse.parse_qs(init_data).get('user', [''])[0])
    telegram_id = str(user_obj.get('id'))

    headers = {
        'User-Agent': meta.get('user_agent', 'Mozilla/5.0 (Linux; Android 14)'),
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Origin': 'https://jvaultminer.world',
        'Referer': 'https://jvaultminer.world/',
        'x-telegram-init-data': init_data,
        'Authorization': f'tma {init_data}'
    }

    # 1. Sync User
    sync_resp = requests.post('https://jvaultminer.world/api/user/sync', json={
        "telegramId": telegram_id,
        "username": user_obj.get('username'),
        "firstName": user_obj.get('first_name'),
        "lastName": user_obj.get('last_name'),
        "referralCode": MASTER_REF,
        "initData": init_data
    }, headers=headers, proxies=proxies, timeout=12).json()

    u = sync_resp.get('user', {})
    user_id = u.get('id')
    if not user_id:
        return {"success": False, "error": sync_resp.get('error', 'Sync failed')}

    # 2. Connect UNIQUE wallet for each account (not master)
    master_key = '[RU] Xxxcalibur +79936124946 2025'
    target_wallet = get_or_create_wallet_for_account(acc_name)
    ton_wallet = u.get('tonWallet')
    
    if not ton_wallet or (ton_wallet == MASTER_WALLET and acc_name != master_key):
        try:
            cw_res = requests.post('https://jvaultminer.world/api/user/connect-wallet', json={
                "address": target_wallet,
                "walletType": "tonconnect",
                "initData": init_data
            }, headers=headers, proxies=proxies, timeout=10).json()
            if cw_res.get('success'):
                ton_wallet = target_wallet
                u['isVerified'] = True
                logger.info(f"[{acc_name}] Connected unique wallet {target_wallet[:12]}... and verified!")
        except Exception as e:
            logger.warning(f"[{acc_name}] Connect unique wallet failed: {e}")

    # 3. Claim Passive Mining (every 6h)
    claimed_cycle = False
    try:
        c_res = requests.post('https://jvaultminer.world/api/user/claim', json={'userId': user_id, 'initData': init_data}, headers=headers, proxies=proxies, timeout=10).json()
        if c_res.get('success'):
            claimed_cycle = True
            logger.info(f"[{acc_name}] Claimed passive mining cycle!")
    except Exception:
        pass

    # 4. Watch Daily Ads (up to 10 ads = +50 JVT)
    ad_watches_done = 0
    current_ad_count = u.get('adWatches', 0)
    if current_ad_count < 10:
        for _ in range(current_ad_count, 10):
            try:
                ad_r = requests.post('https://jvaultminer.world/api/user/watch-ad', json={'clicked': 1, 'initData': init_data}, headers=headers, proxies=proxies, timeout=10).json()
                if ad_r.get('success'):
                    ad_watches_done += 1
                    time.sleep(0.5)
                else:
                    break
            except Exception:
                break
        if ad_watches_done > 0:
            logger.info(f"[{acc_name}] Watched {ad_watches_done} ads (+{ad_watches_done * 5} JVT)!")

    # 5. Tap Mine
    try:
        requests.post('https://jvaultminer.world/api/user/tap-mine', json={'userId': user_id, 'initData': init_data}, headers=headers, proxies=proxies, timeout=10)
    except Exception:
        pass

    # 6. Referral claims
    try:
        requests.post('https://jvaultminer.world/api/user/claim-invite-bonus', json={'userId': user_id, 'initData': init_data}, headers=headers, proxies=proxies, timeout=10)
        requests.post('https://jvaultminer.world/api/user/claim-team-commission', json={'userId': user_id, 'initData': init_data}, headers=headers, proxies=proxies, timeout=10)
    except Exception:
        pass

    # 7. Complete non-channel tasks
    try:
        tasks_resp = requests.get(f'https://jvaultminer.world/api/tasks?userId={user_id}', headers=headers, proxies=proxies, timeout=10).json()
        completed = set(tasks_resp.get('completedTaskIds', []))
        for t in tasks_resp.get('tasks', []):
            tid = t.get('id')
            if tid not in completed:
                cl = requests.post(f'https://jvaultminer.world/api/tasks/claim/{tid}', json={'userId': user_id, 'initData': init_data}, headers=headers, proxies=proxies, timeout=10).json()
                if cl.get('success'):
                    logger.info(f"[{acc_name}] Claimed task {tid} (+{t.get('reward')} JVT)")
    except Exception:
        pass

    # 8. Final sync & withdraw check
    final_sync = requests.post('https://jvaultminer.world/api/user/sync', json={
        "telegramId": telegram_id,
        "username": user_obj.get('username'),
        "firstName": user_obj.get('first_name'),
        "lastName": user_obj.get('last_name'),
        "referralCode": MASTER_REF,
        "initData": init_data
    }, headers=headers, proxies=proxies, timeout=12).json()

    final_u = final_sync.get('user', {})
    final_assets = final_u.get('totalAssets', 0)
    final_wallet = final_u.get('tonWallet') or ton_wallet

    withdrawal_status = None
    if final_assets >= 250:
        logger.info(f"[{acc_name}] Balance {final_assets:.2f} >= 250 JVT! Submitting withdrawal...")
        try:
            w_res = requests.post('https://jvaultminer.world/api/user/withdraw', json={
                'userId': user_id,
                'tonWallet': final_wallet,
                'amount': int(final_assets),
                'initData': init_data
            }, headers=headers, proxies=proxies, timeout=10).json()
            withdrawal_status = w_res
            logger.info(f"[{acc_name}] Withdrawal submitted: {w_res}")
        except Exception as e:
            withdrawal_status = {"error": str(e)}

    return {
        "success": True,
        "userId": user_id,
        "telegramId": telegram_id,
        "username": user_obj.get('username'),
        "totalAssets": final_assets,
        "poolWallet": final_u.get('poolWallet', 0),
        "holdingWallet": final_u.get('holdingWallet', 0),
        "level": final_u.get('level', 1),
        "tonWallet": final_wallet,
        "isVerified": final_u.get('isVerified', False),
        "referredBy": final_u.get('referredBy'),
        "adWatches": final_u.get('adWatches', 0),
        "inviteCount": final_u.get('inviteCount', 0),
        "claimedCycle": claimed_cycle,
        "adsWatched": ad_watches_done,
        "withdrawal": withdrawal_status,
        "lastUpdated": time.time()
    }

async def run_jvault_all(limit=None):
    logger.info("=== Starting JVault Full Farm Cycle ===")
    cfg = json.load(open('config.json'))
    db_accs = json.load(open(r'C:/Users/hoaki/Desktop/RB_Autimatic/accounts_db.json', encoding='utf-8'))
    
    state = {}
    if os.path.exists(STATE_FILE):
        try:
            state = json.load(open(STATE_FILE, encoding='utf-8'))
        except Exception:
            pass

    acc_keys = [k for k in db_accs.keys() if os.path.exists(f'sessions/{k}.session')]
    master_key = '[RU] Xxxcalibur +79936124946 2025'
    if master_key in acc_keys:
        acc_keys.remove(master_key)
        acc_keys.insert(0, master_key)

    if limit:
        acc_keys = acc_keys[:limit]

    processed = 0
    for acc_name in acc_keys:
        processed += 1
        meta = db_accs[acc_name]
        logger.info(f"[{processed}/{len(acc_keys)}] Processing {acc_name}...")
        
        res = await run_jvault_single(acc_name, meta, cfg)
        if res.get('success'):
            state[acc_name] = res
        else:
            logger.warning(f"[{acc_name}] Error: {res.get('error')}")

        if processed % 5 == 0:
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    # Calculate summary
    valid = [v for v in state.values() if v.get('success')]
    total_assets = sum(v.get('totalAssets', 0) for v in valid)
    total_holding = sum(v.get('holdingWallet', 0) for v in valid)
    master_info = state.get(master_key, {})
    ready_count = sum(1 for v in valid if v.get('totalAssets', 0) >= 250)

    summary = {
        "total_accounts": len(valid),
        "total_assets_jvt": round(total_assets, 2),
        "total_holding_jvt": round(total_holding, 2),
        "total_usd_value": round(total_assets * 0.0252, 2),
        "master_assets": round(master_info.get('totalAssets', 0), 2),
        "master_invites": master_info.get('inviteCount', 0),
        "ready_for_withdraw": ready_count,
        "last_run": datetime.utcnow().isoformat(),
        "status": "COMPLETED"
    }
    save_summary(summary)
    logger.info(f"=== Farm Cycle Completed! Total Assets: {total_assets:.2f} JVT (~${total_assets*0.0252:.2f}) | Ready for Withdraw: {ready_count} ===")
    return summary

async def start_jvault_daemon():
    logger.info("JVault Miner background daemon started (6h cycle)...")
    while True:
        try:
            summary = load_summary()
            summary["status"] = "FARMING"
            save_summary(summary)
            await run_jvault_all()
        except Exception as e:
            logger.error(f"Error in JVault farm cycle: {e}")
            summary = load_summary()
            summary["status"] = f"ERROR: {e}"
            save_summary(summary)

        # Sleep 6 hours between cycles
        logger.info("JVault cycle finished. Sleeping for 6 hours (21600s)...")
        await asyncio.sleep(6 * 3600)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--single', type=str, help='Run for single account name')
    parser.add_argument('--limit', type=int, help='Limit number of accounts')
    parser.add_argument('--all', action='store_true', help='Run for all accounts')
    parser.add_argument('--daemon', action='store_true', help='Run 24/7 background daemon')
    args = parser.parse_args()

    cfg = json.load(open('config.json'))
    db_accs = json.load(open(r'C:/Users/hoaki/Desktop/RB_Autimatic/accounts_db.json', encoding='utf-8'))

    if args.single:
        if args.single in db_accs:
            asyncio.run(run_jvault_single(args.single, db_accs[args.single], cfg))
        else:
            print("Account not found in accounts_db.json")
    elif args.daemon:
        asyncio.run(start_jvault_daemon())
    else:
        asyncio.run(run_jvault_all(limit=args.limit))
