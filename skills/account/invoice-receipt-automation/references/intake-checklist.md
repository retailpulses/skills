# Intake Checklist

Use this file when the user mentions invoice, 領収書, or 领收书 but has not yet provided enough material to proceed.

## Minimal Inputs by Goal

### Feasibility Review

Need:

- source file path or pasted table rows
- order ID
- addressee / 宛名
- item name / 商品名
- amount

### PDF Generation

Need:

- source file path
- order ID
- addressee / 宛名
- item name / 商品名
- amount

Optional but often needed:

- issue date when it should not default to today

### OneDrive Output

Need:

- either no extra info and use the default project OneDrive folder
- or an explicit replacement output folder

### External Share Links

Need:

- explicit user request to resume that work
- working Microsoft Graph auth or another approved auth path

## Asking Style

Ask for the smallest missing set only.

Good examples:

- `把导出的 CSV 路径发我，我先核对这批订单能不能开领收书。`
- `目前只缺宛名和金额，补这两项就够继续了。`
- `如果发票日期不是今天，请给我 YYYY-MM-DD。`

Avoid:

- asking for every possible field up front
- asking about share links before the user asks for that step
- asking the user to re-enter fields already visible in the source file
