import os
import json
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.units import mm
import datetime

# Register Japanese font
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))

def create_payslip_pdf(employee_data, month_str, output_path):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # Fonts
    font_bold = "HeiseiKakuGo-W5"
    font_reg = "HeiseiKakuGo-W5"
    
    # Company Info (Retailpulses GK)
    c.setFont(font_reg, 10)
    c.drawString(130*mm, height - 30*mm, "Retailpulses GK")
    c.drawString(130*mm, height - 35*mm, "リテルパルス合同会社")
    c.drawString(130*mm, height - 40*mm, "〒124-0011")
    c.drawString(130*mm, height - 45*mm, "東京都葛飾区四つ木2丁目20番4号")
    c.drawString(130*mm, height - 50*mm, "202号室")
    
    # Employee Info & Month
    c.setFont(font_bold, 12)
    c.drawString(20*mm, height - 35*mm, f"氏名: {employee_data['従業員名']} 様")
    c.drawString(20*mm, height - 45*mm, f"給与年月: {month_str}")
    
    # Title (directly below month)
    c.setFont(font_bold, 18)
    c.drawString(20*mm, height - 58*mm, "給与明細")
    
    # Attendance info (separate row above payment section)
    c.setFont(font_reg, 12)
    c.drawString(20*mm, height - 67*mm, f"勤務日数: {employee_data['勤務日数']} 日")
    
    # Table Header & Borders
    c.setLineWidth(0.5)
    c.line(20*mm, height - 72*mm, 190*mm, height - 72*mm) # Top border
    
    # Sections Header
    c.setFont(font_bold, 11)
    c.drawString(25*mm, height - 80*mm, "【支給項目】 (Earnings)")
    c.drawString(105*mm, height - 80*mm, "【控除項目】 (Deductions)")
    
    # Earnings Data
    c.setFont(font_reg, 10)
    y = height - 90*mm
    c.drawString(25*mm, y, f"基本給: {employee_data['基本給']:,} 円")
    y -= 7*mm
    c.drawString(25*mm, y, f"その他手当: {employee_data['その他手当']:,} 円")
    
    # Deductions Data
    y = height - 90*mm
    c.drawString(105*mm, y, f"健康保険料: {employee_data['健康保険料']:,} 円")
    y -= 7*mm
    c.drawString(105*mm, y, f"厚生年金保険料: {employee_data['厚生年金保険料']:,} 円")
    y -= 7*mm
    c.drawString(105*mm, y, f"雇用保険料: {employee_data['雇用保険料']:,} 円")
    y -= 7*mm
    c.drawString(105*mm, y, f"所得税: {employee_data['所得税']:,} 円")
    y -= 7*mm
    c.drawString(105*mm, y, f"住民税: {employee_data['住民税']:,} 円")
    
    # Summaries
    c.line(20*mm, height - 135*mm, 190*mm, height - 135*mm) # Footer line
    
    total_earnings = employee_data['基本給'] + employee_data['その他手当']
    total_deductions = (employee_data['健康保険料'] + employee_data['厚生年金保険料'] + 
                        employee_data['雇用保険料'] + employee_data['所得税'] + 
                        employee_data['住民税'])
    net_pay = total_earnings - total_deductions
    
    c.setFont(font_bold, 12)
    c.drawString(20*mm, height - 145*mm, f"支給額合計: {total_earnings:,} 円")
    c.drawString(100*mm, height - 145*mm, f"控除額合計: {total_deductions:,} 円")
    
    c.setFont(font_bold, 14)
    c.drawString(20*mm, height - 160*mm, f"差引支給額 (Net): {net_pay:,} 円")
    c.drawString(20*mm, height - 170*mm, f"実支給額 (Payout): {employee_data['実支給額']:,} 円")
    
    c.showPage()
    c.save()

if __name__ == "__main__":
    # Sample run for April 2026 for both employees
    with open('staff_config.json', 'r') as f:
        staff_list = json.load(f)
    
    # For April 2026 with adjusted real payments
    jim_april = staff_list[0].copy()
    jim_april['勤務日数'] = 21
    jim_april['実支給額'] = 331768 # With catch-up
    
    kuno_april = staff_list[1].copy()
    kuno_april['勤務日数'] = 21
    kuno_april['実支給額'] = 186536 # With catch-up
    
    os.makedirs('payslips', exist_ok=True)
    create_payslip_pdf(jim_april, "2026年4月", "payslips/Jim_202604.pdf")
    create_payslip_pdf(kuno_april, "2026年4月", "payslips/Kuno_202604.pdf")
    print("PDF Payslips generated in 'payslips/' folder.")
