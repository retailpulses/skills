import os
import json
import datetime
import requests
from dateutil.relativedelta import relativedelta

# --- 2026 Japanese Public Holidays ---
HOLIDAYS_2026 = {
    datetime.date(2026, 1, 1),   # New Year's Day
    datetime.date(2026, 1, 12),  # Coming of Age Day
    datetime.date(2026, 2, 11),  # National Foundation Day
    datetime.date(2026, 2, 23),  # Emperor's Birthday
    datetime.date(2026, 3, 20),  # Vernal Equinox Day
    datetime.date(2026, 4, 29),  # Showa Day
    datetime.date(2026, 5, 3),   # Constitution Memorial Day
    datetime.date(2026, 5, 4),   # Greenery Day
    datetime.date(2026, 5, 5),   # Children's Day
    datetime.date(2026, 5, 6),   # (Substitute holiday for Constitution Memorial Day)
    datetime.date(2026, 7, 20),  # Marine Day
    datetime.date(2026, 8, 11),  # Mountain Day
    datetime.date(2026, 9, 21),  # Respect for the Aged Day
    datetime.date(2026, 9, 23),  # Autumnal Equinox Day
    datetime.date(2026, 10, 12), # Health and Sports Day
    datetime.date(2026, 11, 3),  # Culture Day
    datetime.date(2026, 11, 23), # Labor Thanksgiving Day
}

def count_work_days(year, month):
    start_date = datetime.date(year, month, 1)
    end_date = start_date + relativedelta(months=1) - datetime.timedelta(days=1)
    
    work_days = 0
    current_date = start_date
    while current_date <= end_date:
        # Check if it's a weekday (Monday=0 to Friday=4)
        if current_date.weekday() < 5:
            # Check if it's NOT a holiday
            if current_date not in HOLIDAYS_2026:
                work_days += 1
        current_date += datetime.timedelta(days=1)
    return work_days, end_date.isoformat()

from generate_payslip_pdf import create_payslip_pdf

def run_payroll(year, month, token, output_dir='payslips'):
    work_days, end_of_month = count_work_days(year, month)
    print(f"Calculated working days for {year}-{month:02d}: {work_days} days. End of month: {end_of_month}")
    
    with open('staff_config.json', 'r') as f:
        staff_list = json.load(f)
        
    os.makedirs(output_dir, exist_ok=True)
    
    for staff in staff_list:
        # Check if staff started (Kuno started Feb 1st)
        if staff['従業員名'] == "久野 由加" and year == 2026 and month == 1:
            print(f"Skipping {staff['従業員名']} for {year}-{month:02d} (started Feb 1st).")
            continue
            
        payload = {
            "従業員名": staff["従業員名"],
            "給与月": end_of_month,
            "勤務日数": work_days,
            "基本給": staff["基本給"],
            "その他手当": staff["その他手当"],
            "健康保険料": staff["健康保険料"],
            "厚生年金保険料": staff["厚生年金保険料"],
            "雇用保険料": staff["雇用保険料"],
            "所得税": staff["所得税"],
            "住民税": staff["住民税"],
            "実支給額": staff["実支給額"],
            "Notes": "所得税: 令和8年分給与所得の源泉徴収税額表（月額表）より算出"
        }
        
        # Check for existing record to avoid duplication
        params = {
            "user_field_names": "true",
            "filter__field_8040570__equal": staff["従業員名"],
            "filter__field_8040571__equal": end_of_month
        }
        headers = {"Authorization": f"Token {token}"}
        search_resp = requests.get("https://api.baserow.io/api/database/rows/table/926319/", headers=headers, params=params)
        
        if search_resp.status_code == 200 and search_resp.json().get('count', 0) > 0:
            print(f"Record for {staff['従業員名']} for {end_of_month} already exists. Skipping Baserow create.")
        else:
            url = "https://api.baserow.io/api/database/rows/table/926319/?user_field_names=true"
            headers["Content-Type"] = "application/json"
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                print(f"Successfully created Baserow record for {staff['従業員名']}.")
            else:
                print(f"Failed to create record for {staff['従業員名']}: {response.text}")
        
        # Generate PDF
        month_label = f"{year}年{month}月"
        safe_name = staff['従業員名'].replace(' ', '_').replace('　', '_')
        pdf_path = os.path.join(output_dir, f"{safe_name}_{year}{month:02d}.pdf")
        try:
            # Important: the payload contains the month-specific work days
            create_payslip_pdf(payload, month_label, pdf_path)
            print(f"Generated PDF: {pdf_path}")
        except Exception as e:
            print(f"Failed to generate PDF for {staff['従業員名']}: {e}")

if __name__ == "__main__":
    import sys
    BASEROW_TOKEN = os.environ.get('BASEROW_TOKEN', 'MhbpMifxj7XOL4V7lzoGSJA6Ju9Vp4Ub')
    
    if len(sys.argv) >= 3:
        year = int(sys.argv[1])
        months = [int(m) for m in sys.argv[2:]]
        for m in months:
            run_payroll(year, m, BASEROW_TOKEN)
    else:
        # Default to April 2026
        run_payroll(2026, 4, BASEROW_TOKEN)
