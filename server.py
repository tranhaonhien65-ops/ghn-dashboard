import http.server
import socketserver
import json
import os
import sys
import threading
import time
from updater import parse_looker_response, parse_metabase_rows, save_and_merge, sync_metabase_live, DATA_FILE

PORT = int(os.environ.get("PORT", 8080))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
BACKLOG_FILE = os.path.join(DIRECTORY, "backlog_data.json")
ORDERS_FILE = os.path.join(DIRECTORY, "orders_data.json")

import gzip

_cache = {
    "orders": {"mtime": 0, "raw": b"", "gz": b""},
    "backlog": {"mtime": 0, "raw": b"", "gz": b""},
    "data": {"mtime": 0, "raw": b"", "gz": b""}
}

def get_cached_file(file_path, key, default_json=b"{}"):
    global _cache
    if not os.path.exists(file_path):
        raw = default_json
        gz = gzip.compress(raw, compresslevel=6)
        return raw, gz
    
    try:
        mtime = os.path.getmtime(file_path)
        entry = _cache.get(key)
        if entry and entry["mtime"] == mtime and entry["raw"]:
            return entry["raw"], entry["gz"]
        
        with open(file_path, "rb") as f:
            raw = f.read()
        gz = gzip.compress(raw, compresslevel=6)
        _cache[key] = {"mtime": mtime, "raw": raw, "gz": gz}
        return raw, gz
    except Exception as e:
        print(f"Cache read error for {key}: {e}")
        return default_json, gzip.compress(default_json)

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def send_json_response(self, raw_bytes, gz_bytes):
        accept_encoding = self.headers.get("Accept-Encoding", "")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        
        if "gzip" in accept_encoding:
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(gz_bytes)))
            self.end_headers()
            self.wfile.write(gz_bytes)
        else:
            self.send_header("Content-Length", str(len(raw_bytes)))
            self.end_headers()
            self.wfile.write(raw_bytes)

    def do_GET(self):
        url_path = self.path.split("?")[0]
        if url_path == "/" or url_path == "" or url_path == "/index.html":
            file_path = os.path.join(DIRECTORY, "index.html")
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.path = "/index.html"
                return super().do_GET()
        elif url_path == "/api/data":
            if os.path.exists(DATA_FILE):
                raw, gz = get_cached_file(DATA_FILE, "data", b"[]")
                # Wrap records if needed
                try:
                    records = json.loads(raw.decode("utf-8"))
                    res = json.dumps({"status": "success", "total_records": len(records), "data": records}, ensure_ascii=False).encode("utf-8")
                    self.send_json_response(res, gzip.compress(res, compresslevel=6))
                except Exception:
                    self.send_json_response(raw, gz)
            else:
                empty = b'{"status":"success","total_records":0,"data":[]}'
                self.send_json_response(empty, gzip.compress(empty))
            return
        elif url_path == "/api/backlog":
            if os.path.exists(BACKLOG_FILE):
                raw, gz = get_cached_file(BACKLOG_FILE, "backlog", b"{}")
                try:
                    bdata = json.loads(raw.decode("utf-8"))
                    res = json.dumps({"status": "success", "data": bdata}, ensure_ascii=False).encode("utf-8")
                    self.send_json_response(res, gzip.compress(res, compresslevel=6))
                except Exception:
                    self.send_json_response(raw, gz)
            else:
                empty = b'{"status":"success","data":{}}'
                self.send_json_response(empty, gzip.compress(empty))
            return
        elif url_path == "/api/orders":
            raw, gz = get_cached_file(ORDERS_FILE, "orders", b'{"orders":[]}')
            self.send_json_response(raw, gz)
            return
        elif url_path == "/health" or url_path == "/ping":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return
        elif url_path == "/api/sync-metabase":
            try:
                count = sync_metabase_live()
                res = json.dumps({"status": "success", "message": f"Đã tự động đồng bộ thành công {count} mã đơn thật từ GHN Metabase!", "total_orders": count}, ensure_ascii=False).encode("utf-8")
                self.send_json_response(res, gzip.compress(res))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                res = {"status": "error", "message": f"Lỗi đồng bộ Metabase: {str(e)}"}
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        else:
            return super().do_GET()

    def do_POST(self):
        if self.path == "/api/update":
            content_length = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_length).decode('utf-8')
            
            try:
                body_json = json.loads(post_body)
                
                if "dataResponse" in body_json or "dataSubset" in str(body_json):
                    new_records = parse_looker_response(body_json)
                elif isinstance(body_json, list):
                    new_records = body_json
                elif "data" in body_json:
                    if isinstance(body_json["data"], dict) and "dataResponse" in body_json["data"]:
                        new_records = parse_looker_response(body_json["data"])
                    else:
                        new_records = body_json["data"]
                else:
                    new_records = parse_looker_response(post_body)
                
                updated_list = save_and_merge(new_records)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                res = {
                    "status": "success",
                    "message": f"Successfully updated {len(new_records)} records! Total dataset: {len(updated_list)} records.",
                    "total_records": len(updated_list),
                    "data": updated_list
                }
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                res = {
                    "status": "error",
                    "message": f"Failed to parse data: {str(e)}"
                }
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif self.path == "/api/orders/update":
            content_length = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_length).decode('utf-8')
            try:
                payload = json.loads(post_body)
                orders_data = {}
                if os.path.exists(ORDERS_FILE):
                    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                        orders_data = json.load(f)
                
                # if raw list of orders provided
                if isinstance(payload, list):
                    if len(payload) > 0 and isinstance(payload[0], list):
                        parsed_orders = parse_metabase_rows(payload)
                        orders_data["orders"] = parsed_orders
                        orders_data["records_count"] = len(parsed_orders)
                    else:
                        orders_data["orders"] = payload
                        orders_data["records_count"] = len(payload)
                elif isinstance(payload, dict):
                    if "data" in payload and isinstance(payload["data"], dict) and "rows" in payload["data"]:
                        parsed_orders = parse_metabase_rows(payload["data"]["rows"])
                        orders_data["orders"] = parsed_orders
                        orders_data["records_count"] = len(parsed_orders)
                    elif "rows" in payload and isinstance(payload["rows"], list):
                        parsed_orders = parse_metabase_rows(payload["rows"])
                        orders_data["orders"] = parsed_orders
                        orders_data["records_count"] = len(parsed_orders)
                    elif "orders" in payload:
                        orders_data["orders"] = payload["orders"]
                        orders_data["records_count"] = len(payload["orders"])
                        if "summary" in payload:
                            orders_data["summary"] = payload["summary"]
                    else:
                        orders_data = payload
                
                with open(ORDERS_FILE, "w", encoding="utf-8") as f:
                    json.dump(orders_data, f, ensure_ascii=False, indent=2)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                res = {
                    "status": "success",
                    "message": f"Cập nhật thành công {len(orders_data.get('orders', []))} mã đơn hàng!",
                    "total_orders": len(orders_data.get('orders', []))
                }
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                res = {"status": "error", "message": str(e)}
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        elif self.path == "/api/orders/toggle-check":
            content_length = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_length).decode('utf-8')
            try:
                payload = json.loads(post_body)
                order_code = payload.get("order_code", "")
                checked = payload.get("checked", True)
                
                if os.path.exists(ORDERS_FILE):
                    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                        orders_data = json.load(f)
                    
                    found = False
                    for ord in orders_data.get("orders", []):
                        if ord.get("order_code") == order_code:
                            ord["checked"] = checked
                            found = True
                            break
                    
                    if found:
                        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
                            json.dump(orders_data, f, ensure_ascii=False, indent=2)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                res = {"status": "success", "order_code": order_code, "checked": checked}
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                res = {"status": "error", "message": str(e)}
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return
        else:
            self.send_error(404, "Endpoint not found")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

def auto_sync_metabase_worker():
    """Background worker that periodically syncs data from GHN Metabase every 15 minutes."""
    # First sleep 5 seconds on startup
    time.sleep(5)
    while True:
        try:
            print("[Auto-Sync Worker] Periodic sync from GHN Metabase...")
            count = sync_metabase_live()
            print(f"[Auto-Sync Worker] Successfully synced {count} live orders!")
        except Exception as e:
            print(f"[Auto-Sync Worker] Sync warning: {e}")
        time.sleep(900) # 15 minutes

def run_server(port=PORT):
    # Launch auto-sync daemon in background
    sync_thread = threading.Thread(target=auto_sync_metabase_worker, daemon=True)
    sync_thread.start()
    print(f"GHN Auto-Sync Worker started (every 15 mins).")

    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print(f"GHN Dashboard Server running at http://0.0.0.0:{port}")
        httpd.serve_forever()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            p = int(sys.argv[1])
        except ValueError:
            p = PORT
    else:
        p = PORT
    run_server(p)
