---
name: invoice-receipt-automation
description: Review and execute Homebliss or Mercari invoice, 領収書, and 领收书 workflows from exported request files. Use when the user asks to assess whether receipts can be issued, generate batch PDF invoices/receipts, save them into OneDrive, place the batch MD report in the same folder, inspect the receipt setup, continue the parked Microsoft Graph share-link work, or guide the user to provide the missing receipt inputs required to proceed.
---

# Invoice Receipt Automation

Use this skill for the current Homebliss / Mercari receipt workflow.

## Data Source

Supabase `sales_orders` table in the `order_management` domain (owned by `retailpulses/OrderMgmt`). Replaces Baserow Orders table 889510.

For order lookup and receipt eligibility, query Supabase PostgREST:

```
GET {SUPABASE_URL}/rest/v1/sales_orders?select=*
Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>
apikey: <SUPABASE_SERVICE_ROLE_KEY>
```

## Reference Docs

Legacy Baserow ERP documentation (for historical reference during migration):

- `/Users/user/Documents/march 2026/Baserow ERP`
- `/Users/user/Documents/march 2026/Baserow ERP/docs/領収書tool.md`
- `/Users/user/Documents/march 2026/Baserow ERP/docs/RECEIPT_SCHEMA_REVIEW_2026-03-19.md`
- `/Users/user/Documents/march 2026/Baserow ERP/docs/EXECUTION_REPORT_receipts_form_2026-03-19.md`
- `/Users/user/Documents/march 2026/Baserow ERP/docs/ONEDRIVE_GRAPH_SHARE_LINKS_SETUP.md`

## Workflow

### 1. Determine order source

1. **If the order exists in Supabase `sales_orders`**: Use the `amount` field if it reflects the customer's total payment.
2. **If the order is NOT in Supabase**: Query Mercari API via VPS:
   - Use the Mercari Shop API to look up the order
   - Extract the payment amount from the Mercari order response
3. Use the Mercari API approach only when the order is absent from Supabase.

### 2. Receipt eligibility checks

- Verify payment status (paid/settled)
- Confirm order is within the eligible date range
- Check for existing receipts (avoid duplicates)

### 3. Generate receipt PDF

- Use the canonical receipt template
- Fill customer info, order amount, date, receipt number
- Export as PDF

### 4. Save and report

- Save PDF to OneDrive receipt folder
- Generate batch MD report in the same folder
- Update receipt tracking in Supabase

## Credentials

- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` — service_role key for reading sales_orders
- Mercari Shop API tokens (for fallback order lookup)
- Microsoft Graph API credentials (for OneDrive upload)
- Legacy `BASEROW_TOKEN` — no longer used for receipt workflow

## Migration Status

The receipt domain is migrating from Baserow ERP to Supabase:

| Component | Baserow (legacy) | Supabase (target) |
|-----------|-----------------|-------------------|
| Orders | Baserow table 889510 | `order_management.sales_orders` |
| Receipt tracking | Baserow form | Pending — needs Supabase table |
| Form/schema | Baserow public form | Pending — needs replacement |

Until the receipt tracking table exists in Supabase, PDF generation and OneDrive upload continue to work independently of the database backend.
