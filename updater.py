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
