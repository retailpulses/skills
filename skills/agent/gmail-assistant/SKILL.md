---
name: gmail-assistant
description: Send, search, and manage Gmail messages with automatic delivery verification and smart draft workflow
always_apply: true
region_scope: INTL
---

# Gmail Assistant

Operate Gmail through **`accio-mcp-cli`** (run from bash). When unsure of a tool name or parameters, run `accio-mcp-cli search gmail` or `accio-mcp-cli toolkit gmail` first, then `accio-mcp-cli call <tool-name> ...` with the Gmail tool names below.

`user_google_email` is **required** for all Google tools. When using the `--json` flag, you **MUST** include `user_google_email` inside the JSON object rather than as a separate flag.
Get it from the user or from prior conversation context.

`query` is **required** for `search_gmail_messages`. If searching the inbox without specific filters, use `label:INBOX`.

---

## Supported Features

| Feature | Tools |
|---------|-------|
| Search messages | `search_gmail_messages` |
| Read single message | `get_gmail_message_content` |
| Batch read messages | `get_gmail_messages_content_batch` |
| Read full thread | `get_gmail_thread_content` / `get_gmail_threads_content_batch` |
| Send message | `send_gmail_message` |
| Download attachment | `get_gmail_attachment_content` |
| Label management | `list_gmail_labels` / `manage_gmail_label` / `modify_gmail_message_labels` / `batch_modify_gmail_message_labels` |
| Filter management | `list_gmail_filters` / `create_gmail_filter` / `delete_gmail_filter` |

---

## Core Workflows

### 1. Sending Email — Draft Preview + Auto Verification

MCP cannot send a draft already saved in the 草稿箱 (Drafts folder).
**Do NOT use `draft_gmail_message`.**

Instead, display the draft directly in the chat for user confirmation, then call
`send_gmail_message` upon approval.

```
User requests sending an email
  │
  ▼
Display draft in chat (To, Cc, Subject, Body) for user preview
  │
  ▼
User confirms → accio-mcp-cli call send_gmail_message
  │
  ▼
Wait ~5 seconds → auto-verify delivery (see below)
```

**Draft display format:**

```
📮 Email Draft

To: alice@example.com
Cc: bob@example.com
Subject: Q1 Sales Report

---
Hi Alice,

Please find attached the Q1 sales report...

Best regards
---

Confirm to send?
```

### 2. Post-Send Delivery Verification (MANDATORY)

After every successful `send_gmail_message` call, you **MUST** automatically verify
delivery. This step is non-optional.

**Immediate Verification Step:**
Wait ~5-10 seconds for Gmail to process, then use a single optimized query:

```bash
accio-mcp-cli call search_gmail_messages --user_google_email "user@example.com" \
  --query 'from:mailer-daemon@googlemail.com (subject:"Delivery Status Notification" OR subject:"找不到地址" OR subject:"Address not found") newer_than:1d' \
  --page_size 5
```

**Evaluation Logic:**
1. **Compare Thread/Subject**: Ensure the bounce corresponds to the message you just sent.
2. **Bounce found** → Read the bounce message, extract the failed recipient address,
   clearly tell the user which address is invalid, and offer to resend with a
   corrected address.
3. **No relevant bounce** → Inform user the email was sent successfully.

**Bounce search query reference:**

| Scenario | Optimized Search Query |
|----------|------------------------|
| Combined Check | `from:mailer-daemon@googlemail.com (subject:"Delivery Status Notification" OR subject:"找不到地址") newer_than:1d` |
| Mailbox full | `from:mailer-daemon@googlemail.com subject:"mailbox full" newer_than:1d` |

---

## Common Examples

### Search messages

```bash
accio-mcp-cli call search_gmail_messages --user_google_email "user@example.com" \
  --query "from:sales@futuretech.com has:attachment newer_than:7d" --page_size 10
```

### Read message content

```bash
accio-mcp-cli call get_gmail_message_content --user_google_email "user@example.com" \
  --message_id "<message_id>"
```

### Batch read multiple messages

```bash
accio-mcp-cli call get_gmail_messages_content_batch \
  --json '{"user_google_email": "user@example.com", "message_ids":["<id1>","<id2>","<id3>"]}'
```

### Send email (HTML format)

```bash
accio-mcp-cli call send_gmail_message \
  --json '{"user_google_email": "user@example.com", "to":"alice@example.com","cc":"bob@example.com","subject":"Q1 Report","body":"<h1>Q1 Report</h1><p>Please see details below...</p>","body_format":"html"}'
```

### Reply within the same thread

```bash
accio-mcp-cli call send_gmail_message \
  --json '{"user_google_email": "user@example.com", "to":"alice@example.com","subject":"Re: Q1 Report","body":"Thanks for the update!","thread_id":"<thread_id>"}'
```

### Create label and archive message

```bash
accio-mcp-cli call manage_gmail_label --user_google_email "user@example.com" \
  --json '{"action":"create","label_name":"Invoices/2026-Q1"}'
```

```bash
accio-mcp-cli call modify_gmail_message_labels --user_google_email "user@example.com" \
  --json '{"message_id":"<message_id>","add_label_ids":["<label_id>"],"remove_label_ids":["INBOX"]}'
```

---

## Important Rules

1. **Never use `draft_gmail_message`** — Drafts cannot be sent via MCP. Always display
   the draft in chat for user confirmation, then call `send_gmail_message` directly.

2. **Always verify after sending** — After every `send_gmail_message` success, wait
   ~5 seconds then search for bounce notifications. This is mandatory and must not
   be skipped.

3. **Always confirm before sending** — Display the full recipient list, subject, and
   body. Only send after the user explicitly confirms.

4. **Gmail search operators** — Standard Gmail search syntax is supported:
   - `from:` / `to:` — sender / recipient
   - `subject:` — subject line
   - `has:attachment` — has attachments
   - `newer_than:1d` / `older_than:7d` — time range
   - `is:unread` — unread messages
   - `label:` — by label
   - `filename:pdf` — by attachment type

5. **Auth failures** — If a call returns an authentication error, guide the user to
   re-authorize via `start_google_auth` (invoke with `accio-mcp-cli call start_google_auth`).

6. **Email Summarization** — When the user asks to "check Gmail", summarize the results by category (e.g., Academic, E-commerce, Tools, Social) to provide a clear overview. Highlight important actions needed (e.g., expiring subscriptions, accepted papers).
