import time
import json
import os
import sys
from updater import sync_metabase_live

def run_sync_once():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Bắt đầu đồng bộ trực tiếp từ Metabase GHN...")
    try:
        total = sync_metabase_live()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ Đồng bộ thành công {total} mã đơn hàng THẬT từ GHN Metabase!")
        return total
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ❌ Lỗi đồng bộ Metabase: {e}")
        return 0

def run_loop(interval_seconds=900): # 15 minutes
    print(f"GHN 24/7 Automated Sync Service Started (Chu kỳ: {interval_seconds//60} phút)...")
    while True:
        run_sync_once()
        time.sleep(interval_seconds)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        run_loop()
    else:
        run_sync_once()
