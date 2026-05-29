import os
import json
import requests
import sys

# Add current folder to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from generate_payslip_docx import create_payslip_docx

token = os.environ.get('BASEROW_TOKEN', 'MhbpMifxj7XOL4V7lzoGSJA6Ju9Vp4Ub')
headers = {
    "Authorization": f"Token {token}",
    "Content-Type": "application/json"
}

# New Remark
REMARK = "差引支給額と実支給額（固定振込額）との差額については、12月の年末調整時または退職時に一括して精算するものとします。"

# Fixed Payouts
JIM_PAYOUT = 331000
KUNO_PAYOUT = 182060
PAYOUT_METHOD = "銀行振り込み"

# April 2026 (Month-end: 2026-04-30)
april_data = {
    40: { # Jim
        "従業員名": "楊　永亮",
        "給与月": "2026-04-30",
        "勤務日数": 21,
        "基本給": 400000,
        "その他手当": 0,
        "健康保険料": 20192,
        "厚生年金保険料": 37515,
        "雇用保険料": 0,
        "所得税": 10750,
        "住民税": 0,
        "実支給額": JIM_PAYOUT,
        "振込方法": PAYOUT_METHOD,
        "Notes": REMARK
    },
    68: { # Kuno
        "従業員名": "久野 由加",
        "給与月": "2026-04-30",
        "勤務日数": 21,
        "基本給": 220000,
        "その他手当": 0,
        "健康保険料": 10835,
        "厚生年金保険料": 20130,
        "雇用保険料": 1100,
        "所得税": 3910,
        "住民税": 0,
        "実支給額": KUNO_PAYOUT,
        "振込方法": PAYOUT_METHOD,
        "Notes": REMARK
    }
}

# May 2026 (Month-end: 2026-05-31)
may_data = {
    42: { # Jim
        "従業員名": "楊　永亮",
        "給与月": "2026-05-31",
        "勤務日数": 18,
        "基本給": 400000,
        "その他手当": 0,
        "健康保険料": 20664,
        "厚生年金保険料": 37515,
        "雇用保険料": 0,
        "所得税": 10750,
        "住民税": 0,
        "実支給額": JIM_PAYOUT,
        "振込方法": PAYOUT_METHOD,
        "Notes": REMARK + "\n令和8年4月分健康保険料より子ども・子育て支援金(0.115%相当)が追加"
    },
    70: { # Kuno
        "従業員名": "久野 由加",
        "給与月": "2026-05-31",
        "勤務日数": 18,
        "基本給": 220000,
        "その他手当": 0,
        "健康保険料": 11088,
        "厚生年金保険料": 20130,
        "雇用保険料": 1100,
        "所得税": 3910,
        "住民税": 0,
        "実支給額": KUNO_PAYOUT,
        "振込方法": PAYOUT_METHOD,
        "Notes": REMARK + "\n令和8年4月分健康保険料より子ども・子育て支援金(0.115%相当)が追加"
    }
}

pdf_dir = "/Users/user/Documents/Retailpulses/10_COMPANY/庶務関係"
os.makedirs(pdf_dir, exist_ok=True)

all_updates = {}
all_updates.update(april_data)
all_updates.update(may_data)

for row_id, payload in all_updates.items():
    # Update Baserow
    url = f"https://api.baserow.io/api/database/rows/table/926319/{row_id}/?user_field_names=true"
    baserow_payload = {
        "基本給": str(payload["基本給"]),
        "その他手当": str(payload["その他手当"]),
        "健康保険料": str(payload["健康保険料"]),
        "厚生年金保険料": str(payload["厚生年金保険料"]),
        "雇用保険料": str(payload["雇用保険料"]),
        "所得税": str(payload["所得税"]),
        "住民税": str(payload["住民税"]),
        "実支給額": str(payload["実支給額"]),
        "振込方法": payload["振込方法"],
        "Notes": payload["Notes"]
    }
    
    resp = requests.patch(url, headers=headers, json=baserow_payload)
    if resp.status_code == 200:
        print(f"Updated Baserow Row {row_id}")
    else:
        print(f"Failed Row {row_id}: {resp.text}")
        
    # Generate Docx
    date_parts = payload["給与月"].split("-")
    year = int(date_parts[0])
    month = int(date_parts[1])
    month_label = f"{year}年{month}月"
    
    safe_name = payload["従業員名"].replace(" ", "_").replace("　", "_")
    docx_filename = f"{safe_name}_{year}{month:02d}.docx"
    docx_path = os.path.join(pdf_dir, docx_filename)
    
    try:
        create_payslip_docx(payload, month_label, docx_path)
        print(f"Generated Docx: {docx_path}")
    except Exception as e:
        print(f"Failed Docx for {payload['従業員名']}: {e}")

print("Payroll reproduction completed.")
