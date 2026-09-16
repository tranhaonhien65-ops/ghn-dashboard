import http.server
import socketserver
import json
import os
import sys
from updater import parse_looker_response, save_and_merge, DATA_FILE

PORT = int(os.environ.get("PORT", 8080))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
BACKLOG_FILE = os.path.join(DIRECTORY, "backlog_data.json")
ORDERS_FILE = os.path.join(DIRECTORY, "orders_data.json")

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        url_path = self.path.split("?")[0]
        if url_path == "/" or url_path == "":
            self.path = "/index.html"
            return super().do_GET()
        elif url_path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            records = []
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    records = json.load(f)

            response = {
                "status": "success",
                "total_records": len(records),
                "data": records
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            return
        elif url_path == "/api/backlog":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            backlog_data = {}
            if os.path.exists(BACKLOG_FILE):
                with open(BACKLOG_FILE, "r", encoding="utf-8") as f:
                    backlog_data = json.load(f)

            response = {
                "status": "success",
                "data": backlog_data
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            return
        elif url_path == "/api/orders":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            orders_data = {"orders": []}
            if os.path.exists(ORDERS_FILE):
                with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                    orders_data = json.load(f)

            self.wfile.write(json.dumps(orders_data, ensure_ascii=False).encode("utf-8"))
            return
        elif url_path == "/health" or url_path == "/ping":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
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
                    orders_data["orders"] = payload
                    orders_data["records_count"] = len(payload)
                elif isinstance(payload, dict):
                    if "orders" in payload:
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

def run_server(port=PORT):
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
