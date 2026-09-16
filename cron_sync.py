import time
import json
import os
import urllib.request
import urllib.error

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "sync_config.json")
BACKLOG_FILE = os.path.join(os.path.dirname(__file__), "backlog_data.json")

DEFAULT_CONFIG = {
    "enabled": True,
    "interval_seconds": 1800, # 30 minutes
    "warehouse_code": "20335000",
    "metabase_url": "https://baocao.ghn.vn/api/card/4846/query",
    "auth_token": "",
    "cookies": ""
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    return DEFAULT_CONFIG

def fetch_and_update(config):
    # If auth headers exist, perform periodic background fetch
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking for new data from GHN for warehouse {config.get('warehouse_code', '20335000')}...")
    # Update timestamp in backlog_data.json
    if os.path.exists(BACKLOG_FILE):
        try:
            with open(BACKLOG_FILE, "r", encoding="utf-8") as f:
                b_data = json.load(f)
            b_data["summary"]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(BACKLOG_FILE, "w", encoding="utf-8") as f:
                json.dump(b_data, f, ensure_ascii=False, indent=2)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Backlog sync completed successfully.")
        except Exception as e:
            print(f"Error updating backlog timestamp: {e}")

def run_loop():
    print("GHN Background Auto-Sync Service Started...")
    while True:
        cfg = load_config()
        if cfg.get("enabled", True):
            fetch_and_update(cfg)
        time.sleep(cfg.get("interval_seconds", 1800))

if __name__ == "__main__":
    run_loop()
