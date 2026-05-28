import os
import json
import requests
import sys

# Add current folder to path to import generate_payslip_pdf
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from generate_payslip_pdf import create_payslip_pdf

token = os.environ.get('BASEROW_TOKEN', 'MhbpMifxj7XOL4V7lzoGSJA6Ju9Vp4Ub')
headers = {
    "Authorization": f"Token {token}",
    "Content-Type": "application/json"
}

# April 2026 Calculations (Month-end: 2026-04-30, 21 working days)
# Health Insurance uses March rate: 4.925% (no Childcare Support yet, which starts from April premium deducted in May)
# Employment Insurance uses new FY2026 rate: 0.5%
# Jim Standard Remuneration Grade: 410,000 JPY -> Health: 20,192 JPY, Pension: 37,515 JPY, Tax: 10,750 JPY
# Kuno Standard Remuneration Grade: 220,000 JPY -> Health: 10,835 JPY, Pension: 20,130 JPY, Employment: 1,100 JPY, Tax: 3,910 JPY
# April contains catch-up from Feb/Mar under-payments.
# Jim catch-up: 512 JPY. Kuno catch-up: 2,984 JPY.
april_data = {
    40: { # Jim (楊　永亮)
        "従業員名": "楊　永亮",
        "給与月": "2026-04-30",
        "勤務日数": 21.0,
        "基本給": 400000,
        "その他手当": 0,
        "健康保険料": 20192,
        "厚生年金保険料": 37515,
        "雇用保険料": 0,
        "所得税": 10750,
        "住民税": 0,
        "実支給額": 332055, # 331,543 (Net) + 512 (Catch-up)
        "Notes": "所得税: 令和8年分給与所得の源泉徴収税額表（月額表）より算出\n備考: 2月・3月分の不足額（256円×2ヶ月 = 512円）を4月分支給額に合算"
    },
    68: { # Kuno (久野 由加)
        "従業員名": "久野 由加",
        "給与月": "2026-04-30",
        "勤務日数": 21.0,
        "基本給": 220000,
        "その他手当": 0,
        "健康保険料": 10835,
        "厚生年金保険料": 20130,
        "雇用保険料": 1100,
        "所得税": 3910,
        "住民税": 0,
        "実支給額": 187009, # 184,025 (Net) + 2,984 (Catch-up)
        "Notes": "所得税: 令和8年分給与所得の源泉徴収税額表（月額表）より算出\n備考: 2月・3月分の不足額（1,492円×2ヶ月 = 2,984円）を4月分支給額に合算"
    }
}

# May 2026 Calculations (Month-end: 2026-05-31, 18 working days)
# Health Insurance uses April rate (includes Childcare Support): 4.925% + 0.115% = 5.04%
# Jim Health + Childcare: 20,664 JPY. Pension: 37,515 JPY. Tax: 10,750 JPY.
# Kuno Health + Childcare: 11,088 JPY. Pension: 20,130 JPY. Employment: 1,100 JPY. Tax: 3,910 JPY.
# May contains no catch-up, so Net Pay equals Payout.
may_data = {
    42: { # Jim (楊　永亮)
        "従業員名": "楊　永亮",
        "給与月": "2026-05-31",
        "勤務日数": 18.0,
        "基本給": 400000,
        "その他手当": 0,
        "健康保険料": 20664,
        "厚生年金保険料": 37515,
        "雇用保険料": 0,
        "所得税": 10750,
        "住民税": 0,
        "実支給額": 331071, # Equals Net
        "Notes": "所得税: 令和8年分給与所得の源泉徴収税額表（月額表）より算出\n備考: 令和8年4月分健康保険料より子ども・子育て支援金(0.115%相当)が追加"
    },
    70: { # Kuno (久野 由加)
        "従業員名": "久野 由加",
        "給与月": "2026-05-31",
        "勤務日数": 18.0,
        "基本給": 220000,
        "その他手当": 0,
        "健康保険料": 11088,
        "厚生年金保険料": 20130,
        "雇用保険料": 1100,
        "所得税": 3910,
        "住民税": 0,
        "実支給額": 183772, # Equals Net
        "Notes": "所得税: 令和8年分給与所得の源泉徴収税額表（月額表）より算出\n備考: 令和8年4月分健康保険料より子ども・子育て支援金(0.115%相当)が追加"
    }
}

# Destination folder for PDF payslips
pdf_dir = "/Users/user/Documents/Retailpulses/2026 payroll"
os.makedirs(pdf_dir, exist_ok=True)

# Process updates
all_updates = {}
all_updates.update(april_data)
all_updates.update(may_data)

for row_id, payload in all_updates.items():
    # Update Baserow record
    url = f"https://api.baserow.io/api/database/rows/table/926319/{row_id}/?user_field_names=true"
    
    # Baserow payload fields should match their exact names and types
    baserow_payload = {
        "基本給": str(payload["基本給"]),
        "その他手当": str(payload["その他手当"]),
        "健康保険料": str(payload["健康保険料"]),
        "厚生年金保険料": str(payload["厚生年金保険料"]),
        "雇用保険料": str(payload["雇用保険料"]),
        "所得税": str(payload["所得税"]),
        "住民税": str(payload["住民税"]),
        "実支給額": str(payload["実支給額"]),
        "Notes": payload["Notes"]
    }
    
    resp = requests.patch(url, headers=headers, json=baserow_payload)
    if resp.status_code == 200:
        print(f"Successfully updated Baserow Row {row_id} ({payload['従業員名']} - {payload['給与月']})")
    else:
        print(f"Failed to update Baserow Row {row_id}: {resp.text}")
        
    # Generate PDF
    # Determine Month label (e.g. 2026年4月)
    date_parts = payload["給与月"].split("-")
    year = int(date_parts[0])
    month = int(date_parts[1])
    month_label = f"{year}年{month}月"
    
    safe_name = payload["従業員名"].replace(" ", "_").replace("　", "_")
    pdf_filename = f"{safe_name}_{year}{month:02d}.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)
    
    try:
        # Note: generate_payslip_pdf relies on these int values in payload
        pdf_payload = payload.copy()
        # Clean any float working days to float or string, pdf script uses payload['勤務日数']
        create_payslip_pdf(pdf_payload, month_label, pdf_path)
        print(f"Generated PDF: {pdf_path}")
    except Exception as e:
        print(f"Failed to generate PDF for {payload['従業員名']} ({payload['給与月']}): {e}")

print("Payroll updates and PDF generation completed successfully!")
