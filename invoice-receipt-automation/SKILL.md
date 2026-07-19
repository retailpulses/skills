---
name: invoice-receipt-automation
description: Review and execute Homebliss or Mercari invoice, 領収書, and 领收书 workflows from exported request files. Use when the user asks to assess whether receipts can be issued, generate batch PDF invoices/receipts, save them into OneDrive, place the batch MD report in the same folder, inspect the existing receipt setup, continue the parked Microsoft Graph share-link work, or guide the user to provide the missing receipt inputs required to proceed.
---

> **Migration note (2026-07-18):** This skill still references Baserow for receipt/order data (Orders table 889510, Baserow ERP docs). The receipt domain is separate from `product_catalog` and requires its own Baserow→Supabase migration. Until that migration is complete, continue using the Baserow paths documented below.

# Invoice Receipt Automation

Use this skill for the current Homebliss / Mercari receipt workflow stored under:

- `/Users/user/Documents/march 2026/Baserow ERP`

## Quick Start

1. If the user provides an exported request file, inspect it first.
2. If the user asks whether invoice / 領収書 issuance is possible, compare the file against the current receipt schema and sample layout.
3. If the user wants actual output, use the batch generator script.
4. Save PDFs to the OneDrive folder for that run date and ensure the MD report sits in the same folder.

## Intake Rule

Do not jump straight into generation if the request is underspecified.

First determine whether the user has already provided enough information to:

- review feasibility only
- generate PDFs now
- save outputs to OneDrive
- produce a batch report with order IDs and link status

If any required input is missing, ask for the smallest missing set in one concise message instead of a long questionnaire.

## Core Files

Read these only when relevant:

- `docs/領収書tool.md`
  Use for the original project scope and current business rules.
- `docs/RECEIPT_SCHEMA_REVIEW_2026-03-19.md`
  Use for the live Baserow receipt schema, public form status, and sample-field rationale.
- `docs/EXECUTION_REPORT_receipts_form_2026-03-19.md`
  Use for the current published Baserow form and field exposure.
- `docs/ONEDRIVE_GRAPH_SHARE_LINKS_SETUP.md`
  Read only when the user reopens external share-link automation.
- `references/intake-checklist.md`
  Read when the user mentions invoice / 領収書 / 领收书 but has not yet provided enough fields or files to proceed.

## Amount Sourcing Rule (CRITICAL — Mercari Orders)

When generating receipts for Mercari orders, **always use `totalPrice` from the Mercari Shop API**, not `unitPrice`.

- **`unitPrice`** = product price only (excludes shipping)
- **`totalPrice`** = full amount customer paid (product + shipping + any fees)
- **Rule**: Receipts must reflect the exact amount paid by the customer. Using `unitPrice` alone will produce an under-invoiced receipt.

### How to source the amount:

1. **If the order exists in Baserow Orders table (889510)**: Use the `Amount` field if it reflects the customer's total payment.
2. **If the order is NOT in Baserow**: Query Mercari API via VPS:
   ```graphql
   query q($id: ID!) {
     orderTransaction(id: $id) {
       totalPrice
       products { unitPrice purchasedQuantity }
     }
   }
   ```
   Always use `totalPrice` (e.g., ¥18,094) not `unitPrice` (e.g., ¥15,494).
3. **If the user provides the amount directly**: Use the user-provided value but confirm it matches the order total if uncertain.

### Pre-generation verification:

Before running the PDF generator, verify the amount by:
- Checking Baserow Orders table, OR
- Querying Mercari API for `totalPrice`, OR
- Confirming with the user if there's any discrepancy.

**Never generate a receipt PDF without confirming the correct total amount.**

## Working Scripts

- `scripts/receipts/generate-receipts-batch.js`
  Use to generate fixed-layout Japanese receipt PDFs from the exported CSV and write the report into both the project output folder and the OneDrive run folder.
- `scripts/receipts/create-onedrive-share-links.js`
  Keep parked unless the user explicitly resumes OneDrive external share-link work.
- `scripts/receipts/create-receipts-schema.js`
  Use when schema drift or missing Baserow fields must be reviewed.
- `scripts/receipts/configure-receipts-form-view.js`
  Use when the receipt request form must be reviewed or republished.

## Default Receipt Workflow

### 1. Validate the source file

Check whether the file includes, at minimum:

- order ID
- addressee / 宛名
- item name / 商品名
- amount

If these exist, the current fixed template can be generated.

If the file is missing one or more of these fields, stop generation and ask the user for the missing values.

### 1A. Ask for missing information

Use this checklist to decide what to request.

For feasibility review only, require:

- source file path or pasted rows
- order ID
- addressee
- item name
- amount

For PDF generation, require:

- source file path
- order ID
- addressee
- item name
- amount
- issue date if it should not default to today

For OneDrive delivery, require:

- confirmation to use the default OneDrive folder or a replacement output folder

For share-link work, require:

- explicit user request to resume it
- actual Microsoft Graph auth or other approved auth path

When information is missing, ask narrowly. Prefer prompts like:

- `请把导出的 CSV/XLSX 路径发我，我先核字段是否够开票。`
- `现在还缺宛名和金额；把这两列补给我后我再生成 PDF。`
- `如果发票日期不是今天，请直接给我一个 YYYY-MM-DD 日期。`
- `如果 OneDrive 不用默认目录，请给我目标文件夹路径。`

Do not ask for fields that are already present in the file.
Do not ask about external share URLs unless the user explicitly wants that step now.

### 2. Generate PDFs

Run:

```bash
cd '/Users/user/Documents/march 2026/Baserow ERP'
npm run receipt:batch -- --source-csv='/absolute/path/to/source.csv' --run-date=YYYY-MM-DD --issue-date=YYYY-MM-DD
```

Default output pattern:

- OneDrive PDFs:
  `/Users/user/Library/CloudStorage/OneDrive-Personal/ドキュメント/March 2026/領収書/<run-date>/`
- Project report:
  `output/receipts/batch/<run-date>/RECEIPTS_BATCH_REPORT_<run-date>.md`
- OneDrive report:
  same folder as the PDFs

### 3. Verify outputs

Check:

- all expected PDFs exist
- the batch MD file exists in the same OneDrive folder
- the report lists order IDs and current share-link status

### 4. Report current limitation correctly

As of the current working setup:

- PDF generation works
- saving into OneDrive works
- OneDrive external share links are not yet part of the normal finished path

Do not imply that public share URLs were generated unless the Graph workflow has actually been run and verified.

## Baserow Guidance

Use the existing Baserow setup only when the user asks to review intake feasibility or continue the data-entry workflow. The current known live state from project docs is:

- `Receipts` table exists
- customer webform exists
- receipt intake fields are already defined

Treat Baserow review and PDF generation as separate steps. The current reliable production path is CSV review plus batch PDF generation.

## Baserow Access

Use the live Baserow APIs directly when checking receipt intake, schema drift, or row-level status.

- Authenticate row operations with `Authorization: Token <database token>`.
- Use `user_field_names=true` for readable field keys.
- Page through rows with `size=200&page=<n>` when reading a full table.
- Treat database-token row access and JWT schema access as separate paths.
- Use the current live schema before assuming any receipt field names or form mappings.
- Keep schema review, row review, and PDF generation as separate steps.
- Do not invent missing form fields or receipt values when the live data does not supply them.

## Share-Link Guidance

Only resume share-link work if the user explicitly asks.

When that happens:

1. Read `docs/ONEDRIVE_GRAPH_SHARE_LINKS_SETUP.md`.
2. Prefer `Microsoft Graph createLink` over browser automation.
3. Require actual auth before claiming success.
4. Update the existing batch report instead of writing a disconnected report elsewhere.
