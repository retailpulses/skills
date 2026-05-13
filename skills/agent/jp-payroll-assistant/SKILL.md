---
name: jp-payroll-assistant
description: Prepare monthly Japanese payroll slips (給与明細) in Baserow. This skill calculates working days (excluding weekends and Japanese public holidays), manages deductions for compliance, and creates records in the '給与明細' table. Use this skill whenever the user asks for "payroll", "payslip", "給与明細", or "monthly salary calculation".
---

# Japanese Payroll Assistant

This skill automates the creation of Japanese payroll records in Baserow with precise holiday-aware working day calculations.

## Database Location
- **Database**: Backoffice (ID: 414826)
- **Table**: 給与明細 (ID: 926319)

## Core Workflow

1. **Calculate Working Days**:
   - For the target month, identify all business days (Monday to Friday).
   - Exclude Japanese National Holidays.
   - For 2026, reference the established holiday list (or use `get_time` and `web_search` for the current year).

2. **Retrieve Salary Data**:
   - Maintain a local `staff_config.json` in the skill's root directory containing:
     - 従業員名 (Employee Name)
     - 基本給 (Base Salary)
     - その他手当 (Other Allowances)
     - 健康保険料 (Health Insurance)
     - 厚生年金保険料 (Pension)
     - 雇用保険料 (Employment Insurance)
     - 所得税 (Income Tax)
     - 住民税 (Inhabitant Tax)

3. **Data Entry**:
   - Create a new record in Baserow table 926319 using the `baserow-database-manager` or direct `curl` calls with the database token.

## 2026 Japanese Public Holidays (Reference)
- Jan 1 (New Year's Day)
- Jan 12 (Coming of Age Day)
- Feb 11 (National Foundation Day)
- Feb 23 (Emperor's Birthday)
- Mar 20 (Vernal Equinox Day)
- Apr 29 (Showa Day)
- May 3 (Constitution Memorial Day) - Observed May 6
- May 4 (Greenery Day)
- May 5 (Children's Day)
- Jul 20 (Marine Day)
- Aug 11 (Mountain Day)
- Sep 21 (Respect for the Aged Day)
- Sep 23 (Autumnal Equinox Day)
- Oct 12 (Health and Sports Day)
- Nov 3 (Culture Day)
- Nov 23 (Labor Thanksgiving Day)

## Instruction for Calculation
- Use a script (e.g., `calculate_workdays.py`) to count days where:
  - Day is not Saturday or Sunday.
  - Day is not in the holiday list.
- **Simplest Assumption**: We assume all business days are worked unless the user specifies otherwise.

4. **Generate PDF Payslips**:
   - Use `generate_payslip_pdf.py` to produce professional PDF copies for printing or records.
   - Includes Company Name and Address:
     - Retailpulses GK（リテルパルス合同会社）
     - 東京都葛飾区四つ木2丁目20番4号 202号室

## Output
- Confirm the number of working days calculated.
- List the total Net Pay (差引支給額) for each staff member.
- Provide a link to the Baserow table.
- Generate and provide links to PDF payslips in the `payslips/` directory.
