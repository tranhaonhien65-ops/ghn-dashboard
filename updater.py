import json
import os
import re

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

def parse_looker_response(raw_input):
    """Parses Looker Studio batchedDataV2 response and returns clean records."""
    if isinstance(raw_input, str):
        # Extract the JSON object portion if surrounded by curl or other text
        s_idx = raw_input.find('{')
        e_idx = raw_input.rfind('}')
        if s_idx != -1 and e_idx != -1:
            raw_input = raw_input[s_idx:e_idx+1]
        data = json.loads(raw_input)
    else:
        data = raw_input

    # Navigate to column data
    data_response = data.get("dataResponse", [])
    if not data_response:
        raise ValueError("Invalid Looker Studio JSON structure: missing 'dataResponse'")
    
    subsets = data_response[0].get("dataSubset", [])
    if not subsets:
        raise ValueError("Invalid Looker Studio JSON: missing 'dataSubset'")
    
    table = subsets[0]["dataset"]["tableDataset"]
    cols = table["column"]

    # Identify column indices
    # col 1: region, col 2: timeslot, col 3: date, col 4: volume, col 5: %volume, col 6: leadtime
    region_values = cols[1]["stringColumn"]["values"]
    timeslot_values = cols[2]["stringColumn"]["values"]
    date_values = cols[3]["stringColumn"]["values"]
    volume_values = [int(v) for v in cols[4]["longColumn"]["values"]]
    pct_volume_values = cols[5]["doubleColumn"]["values"]
    lead_time_values = cols[6]["doubleColumn"]["values"]

    records = []
    for i in range(len(region_values)):
        raw_date = date_values[i]
        d_parts = raw_date.split(" - ")
        iso_date = d_parts[0].strip()
        day_name = d_parts[1].strip() if len(d_parts) > 1 else ""

        records.append({
            "region": region_values[i],
            "timeslot": timeslot_values[i],
            "raw_date": raw_date,
            "iso_date": iso_date,
            "day_name": day_name,
            "volume": volume_values[i],
            "pct_volume": round(pct_volume_values[i] * 100, 2),
            "lead_time": round(lead_time_values[i], 2)
        })
    return records

def parse_metabase_rows(rows):
    """Converts raw Metabase rows array into structured order objects."""
    formatted_orders = []
    for idx, r in enumerate(rows):
        if not isinstance(r, list):
            continue
        ma_don = str(r[0]) if len(r) > 0 and r[0] is not None else ''
        ma_kien = str(r[1]) if len(r) > 1 and r[1] is not None else ''
        ma_kho = str(r[2]) if len(r) > 2 and r[2] is not None else '20335000'
        kho = str(r[3]) if len(r) > 3 and r[3] is not None else 'Kho Trung Chuyển Bình Định'
        phan_loai = str(r[4]) if len(r) > 4 and r[4] is not None else 'Đang luân chuyển đến KTC'
        nhom = str(r[5]) if len(r) > 5 and r[5] is not None else 'Đang luân chuyển đến KTC'
        tinh_tp = str(r[6]) if len(r) > 6 and r[6] is not None else 'Bình Định'
        vao_tt = str(r[7]) if len(r) > 7 and r[7] is not None else ''
        
        so_gio = 0.0
        if len(r) > 8 and r[8] is not None:
            try:
                so_gio = round(float(r[8]), 1)
            except:
                so_gio = 0.0
                
        khung_gio = str(r[9]) if len(r) > 9 and r[9] is not None else ''
        
        trong_luong = 0.0
        if len(r) > 10 and r[10] is not None:
            try:
                trong_luong = round(float(r[10]), 2)
            except:
                trong_luong = 0.0
                
        formatted_orders.append({
            'stt': idx + 1,
            'ma_don': ma_don,
            'ma_kien': ma_kien,
            'ma_kho': ma_kho,
            'kho': kho,
            'phan_loai': phan_loai,
            'nhom': nhom,
            'tinh_tp': tinh_tp,
            'vao_trang_thai_luc': vao_tt,
            'so_gio_da_nam': so_gio,
            'khung_gio': khung_gio,
            'trong_luong_kg': trong_luong,
            'checked': False
        })
    return formatted_orders

def save_and_merge(records):
    existing_map = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                for r in existing:
                    key = (r.get("region", ""), r.get("iso_date", ""), r.get("timeslot", ""))
                    existing_map[key] = r
        except Exception as e:
            print(f"Warning reading existing data: {e}")

    for r in records:
        key = (r.get("region", ""), r.get("iso_date", ""), r.get("timeslot", ""))
        existing_map[key] = r

    sorted_records = sorted(list(existing_map.values()), key=lambda x: (x["iso_date"], x["timeslot"]))

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_records, f, ensure_ascii=False, indent=2)

    return sorted_records

def sync_metabase_live():
    """Calls GHN Metabase Token API, fetches card 4885, and updates orders_data.json & backlog_data.json."""
    import urllib.request
    import datetime

    token_url = 'https://baocao-v2-api.ghn.vn/baocao-service/report/dashboard/metabase-token'
    token_headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json',
        'origin': 'https://baocao.ghn.vn',
        'referer': 'https://baocao.ghn.vn/',
        'remote-ip': '14.254.55.151',
        'token': '4a90250c-0485-4ec9-8a12-efcbcf76624e',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'
    }
    token_data = json.dumps({'user_id': 3007413, 'dashboard_id': 317}).encode('utf-8')
    req = urllib.request.Request(token_url, data=token_data, headers=token_headers, method='POST')

    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        jwt_token = res['data']['token']

    query_url = f'https://data-bi.ghn.vn/api/embed/dashboard/{jwt_token}/dashcard/6243/card/4885?parameters=%7B%22kho%22%3Anull%2C%22ma_kho%22%3A%5B%2220335000%22%5D%2C%22phan_loai%22%3Anull%7D'
    query_headers = {
        'accept': 'application/json',
        'content-type': 'application/json',
        'referer': 'https://data-bi.ghn.vn/embed/sdk/v1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36',
        'x-metabase-client': 'embedding-simple',
        'x-metabase-embed-referrer': 'https://baocao.ghn.vn/dashboards/6a71852ca20df68be00411c2',
        'x-metabase-locale': 'en'
    }
    req2 = urllib.request.Request(query_url, headers=query_headers, method='GET')
    with urllib.request.urlopen(req2, timeout=60) as resp2:
        query_res = json.loads(resp2.read().decode('utf-8'))
        rows = query_res.get('data', {}).get('rows', [])

    formatted_orders = []
    unique_packages = set()
    total_weight = 0.0

    stage_list = [
        'Chờ phân loại',
        'Đang phân loại',
        'Chờ xuất kiện chuyển tiếp',
        'Chờ xuất',
        'Đang luân chuyển đến KTC',
        'Tồn khác trong kho'
    ]
    matrix_stage = {s: {'h0_6': 0, 'h6_12': 0, 'h12_24': 0, 'h24_48': 0, 'h48_72': 0, 'h72_96': 0, 'h_over96': 0, 'h_over48': 0, 'tong': 0} for s in stage_list}
    wh_matrix = {'h0_6': 0, 'h6_12': 0, 'h12_24': 0, 'h24_48': 0, 'h48_72': 0, 'h72_96': 0, 'h_over96': 0, 'h_over48': 0, 'tong': 0}

    for idx, r in enumerate(rows):
        ma_don = str(r[0]) if len(r) > 0 and r[0] is not None else ''
        ma_kien = str(r[1]) if len(r) > 1 and r[1] is not None else ''
        if ma_kien: unique_packages.add(ma_kien)
        ma_kho = str(r[2]) if len(r) > 2 and r[2] is not None else '20335000'
        kho = str(r[3]) if len(r) > 3 and r[3] is not None else 'Kho Trung Chuyển Bình Định'
        phan_loai = str(r[4]) if len(r) > 4 and r[4] is not None else 'Đang luân chuyển đến KTC'
        nhom = str(r[5]) if len(r) > 5 and r[5] is not None else 'Đang luân chuyển đến KTC'
        tinh_tp = str(r[6]) if len(r) > 6 and r[6] is not None else 'Bình Định'
        vao_tt = str(r[7]) if len(r) > 7 and r[7] is not None else ''
        
        so_gio = 0.0
        if len(r) > 8 and r[8] is not None:
            try: so_gio = round(float(r[8]), 1)
            except: so_gio = 0.0
            
        if so_gio <= 6:
            khung_gio = '0-6h'
            h_key = 'h0_6'
        elif so_gio <= 12:
            khung_gio = '6-12h'
            h_key = 'h6_12'
        elif so_gio <= 24:
            khung_gio = '12-24h'
            h_key = 'h12_24'
        elif so_gio <= 48:
            khung_gio = '24-48h'
            h_key = 'h24_48'
        elif so_gio <= 72:
            khung_gio = '48-72h'
            h_key = 'h48_72'
        elif so_gio <= 96:
            khung_gio = '72-96h'
            h_key = 'h72_96'
        else:
            khung_gio = 'trên 96h'
            h_key = 'h_over96'
            
        trong_luong = 0.0
        if len(r) > 10 and r[10] is not None:
            try:
                trong_luong = round(float(r[10]), 2)
                total_weight += trong_luong
            except: trong_luong = 0.0
            
        st_match = phan_loai
        if phan_loai not in matrix_stage:
            if 'phân loại' in phan_loai.lower(): st_match = 'Đang phân loại' if 'đang' in phan_loai.lower() else 'Chờ phân loại'
            elif 'chuyển tiếp' in phan_loai.lower(): st_match = 'Chờ xuất kiện chuyển tiếp'
            elif 'xuất' in phan_loai.lower() or 'rời kho' in phan_loai.lower(): st_match = 'Chờ xuất'
            elif 'luân chuyển' in phan_loai.lower(): st_match = 'Đang luân chuyển đến KTC'
            else: st_match = 'Tồn khác trong kho'
            
        matrix_stage[st_match][h_key] += 1
        matrix_stage[st_match]['tong'] += 1
        if so_gio > 48:
            matrix_stage[st_match]['h_over48'] += 1
            wh_matrix['h_over48'] += 1

        wh_matrix[h_key] += 1
        wh_matrix['tong'] += 1

        formatted_orders.append({
            'stt': idx + 1,
            'ma_don': ma_don,
            'ma_kien': ma_kien,
            'ma_kho': ma_kho,
            'kho': kho,
            'phan_loai': phan_loai,
            'nhom': nhom,
            'tinh_tp': tinh_tp,
            'vao_trang_thai_luc': vao_tt,
            'so_gio_da_nam': so_gio,
            'khung_gio': khung_gio,
            'trong_luong_kg': trong_luong,
            'checked': False
        })

    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    orders_file = os.path.join(os.path.dirname(__file__), "orders_data.json")
    backlog_file = os.path.join(os.path.dirname(__file__), "backlog_data.json")

    orders_output = {
        'title': 'Chi tiết mức mã đơn',
        'ma_kho': '20335000',
        'kho': 'Kho Trung Chuyển Bình Định',
        'last_updated': now_str,
        'total_orders': len(formatted_orders),
        'total_packages': len(unique_packages),
        'total_weight_kg': round(total_weight, 2),
        'records_count': len(formatted_orders),
        'orders': formatted_orders
    }
    with open(orders_file, 'w', encoding='utf-8') as f:
        json.dump(orders_output, f, ensure_ascii=False, indent=2)

    matrix_rows = []
    for s in stage_list:
        m = matrix_stage[s]
        matrix_rows.append({
            'phan_loai': s,
            'h0_6': m['h0_6'],
            'h6_12': m['h6_12'],
            'h12_24': m['h12_24'],
            'h24_48': m['h24_48'],
            'h48_72': m['h48_72'],
            'h72_96': m['h72_96'],
            'h_over96': m['h_over96'],
            'h_over48': m['h_over48'],
            'tong': m['tong']
        })
        
    backlog_output = {
        'title': 'Tồn theo phân loại × số giờ đã nằm',
        'ma_kho': '20335000',
        'kho': 'Kho Trung Chuyển Bình Định',
        'last_updated': now_str,
        'total_orders': len(formatted_orders),
        'total_packages': len(unique_packages),
        'total_weight_kg': round(total_weight, 2),
        'ton_theo_phan_loai': matrix_rows,
        'ton_theo_kho': [
            {
                'ma_kho': '20335000',
                'kho': 'Kho Trung Chuyển Bình Định',
                'h0_6': wh_matrix['h0_6'],
                'h6_12': wh_matrix['h6_12'],
                'h12_24': wh_matrix['h12_24'],
                'h24_48': wh_matrix['h24_48'],
                'h48_72': wh_matrix['h48_72'],
                'h72_96': wh_matrix['h72_96'],
                'h_over96': wh_matrix['h_over96'],
                'h_over48': wh_matrix['h_over48'],
                'tong': wh_matrix['tong']
            }
        ]
    }
    with open(backlog_file, 'w', encoding='utf-8') as f:
        json.dump(backlog_output, f, ensure_ascii=False, indent=2)

    return len(formatted_orders)

