---
name: mercari-settlement-pdf
description: Generate a Mercari settlement PDF (売上金精算書) for a given set of months, amounts, and a settlement number (INV-YYYY-MM). Use this skill when the user says "开具精算书", "生成结算PDF", or provides a list of monthly settlement amounts for "合同会社リンセイ".
---

# Mercari Settlement PDF Generator

Use this skill to create a professional one-page Japanese settlement PDF (売上金精算書) for Mercari Shops.

## Core Information
- **Issuer**: リテルパルス合同会社
- **Recipient**: 合同会社リンセイ (〒124-0011 東京都葛飾区四つ⽊2-20-4-301)
- **Bank Info**: 楽天銀行, 第四営業支店 (254), 普通 7715880, リテルパルス（ド

## Workflow

1.  **Collect Inputs**:
    - **Months and Amounts**: A list of months (e.g., "2026年3月") and their corresponding amounts (e.g., "1,686,796").
    - **Settlement Number**: (e.g., "INV-2026-03").
    - **Issue Date**: Default to today if not provided.

2.  **Generate PDF**:
    - Prepare a JSON or CLI call to the script `scripts/generate_pdf.js`.
    - Use the Playwright runtime in the `Baserow ERP` directory: `/Users/user/Documents/march 2026/Baserow ERP/`.

3.  **Deliver PDF**:
    - Save the output to `/Users/user/Documents/Mercari/売上金精算書_[番号].pdf`.
    - Confirm the file path to the user.

## Running the Script
Run the script using the Node.js environment in the `Baserow ERP` project to ensure dependencies (playwright) are available.

```bash
cd "/Users/user/Documents/march 2026/Baserow ERP/"
node "/Users/user/.accio/accounts/7085446805/agents/DID-F456DA-2B0D4C/agent-core/skills/mercari-settlement-pdf/scripts/generate_pdf.js" \
  --number="INV-2026-02" \
  --issue-date="2026年4月12日" \
  --data='[{"month":"2026年1月分","amount":"951,722"},{"month":"2026年2月分","amount":"813,483"},{"month":"2026年3月分","amount":"1,686,796"}]' \
  --output="/Users/user/Documents/Mercari/売上金精算书_INV-2026-02.pdf"
```
