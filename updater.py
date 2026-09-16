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
