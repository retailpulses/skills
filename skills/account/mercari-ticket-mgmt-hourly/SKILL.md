---
name: mercari-ticket-mgmt
description: Process one Mercari Shop `未返信` transaction-message batch on demand, classify greeting-only vs real vs suspicious messages, update Baserow Tickets, and emit the greeting-only/reply report.
---
# Mercari Ticket Mgmt

## Overview

Use this skill for on-demand Mercari Shop `未返信` `取引メッセージ` handling.
It keeps AI usage minimal, routes only real work into Baserow `Tickets`, writes a run log into Baserow table `916585`, attaches a Markdown deliverable grouped by shop, and ends each run with a concise operational report.

## Project Reference

- Baserow project row: `https://baserow.io/database/410005/table/916456/1801049/row/67`
- Project name: `Mercari Ticket Mgmt`
- Keep the skill aligned with that project record and its backlog items when updating rules or deliverables.
- Linked knowledge row: `https://baserow.io/database/393156/table/897440/1765041/row/35`
- Use that knowledge row as the first-line handling reference for `不具合` cases.

## Backlog Requirements

- `Product quality 1st line handling`
  - When a customer reports a product quality issue (`不具合`), draft the first response by:
    - writing a customer-specific reply
    - offering DIY check advice if applicable
    - inviting the customer to submit the ticket form if the issue is still unresolved
  - Refer to the linked knowledge base entry in the backlog item for the exact response guidance.

## Workflow

1. Fetch the current batch of Mercari Shop transactions marked `未返信`.
   - `未返信` is the platform status that defines the scope.
2. Dedupe against prior runs by transaction/message IDs if available.
3. Drop ineligible conversations first:
   - do not act on canceled transactions
   - do not treat historical closed-thread greetings or information-only updates as actionable unless they are still in `未返信`
4. Classify each eligible message as one of:
  - `greeting_only`
  - `information-only`
  - `real_ticket`
  - `suspicious`
5. Apply the minimum action for each class:
  - `greeting_only`: send the base acknowledgment reply only; do not create a Baserow ticket row.
  - `information-only`: send the base acknowledgment reply only; do not create a Baserow ticket row.
  - `real_ticket`: create or upsert into Baserow `Tickets`, send the acknowledgment template, and draft a reply
  - `suspicious`: create or upsert into Baserow `Tickets`, send the acknowledgment template, and draft a reply
6. Use AI only when deterministic rules or templates are not sufficient for stable handling.
7. Finish the run by writing the required report, a Baserow log entry, and a Markdown deliverable grouped by shop.

## Classification Rules

Keep the classifier conservative.

- `greeting_only` means short acknowledgement or greeting with no issue, request, or logistics detail.
- `greeting_only` also includes polite acknowledgement/thanks messages that do not add a new issue or request, such as:
  - `かしこまりました、ご対応ありがとうございます。到着を心よりお待ちしております。`
  - `ありがとうございます！よろしくお願いいたします！`
  - `了解しました。よろしくお願いします。`
- `information-only` means the buyer is providing a factual update or status note with no request or complaint, such as:
  - payment date / payment timing notices
  - shipping or receipt timing updates
  - travel or availability updates that only explain when they can check or respond
- if the message includes both information and any request, complaint, or other support intent, it is not `information-only`
- `real_ticket` means the message contains a problem, request, complaint, refund, replacement, return, payment, or similar support intent.
- `suspicious` means the message is not clearly greeting-only and not clearly a real ticket.

If uncertain, choose `suspicious` rather than suppressing the message.

Inquiry reply SOP:
- For inquiry drafting, always check linked `Knowledge` first and use it as the primary policy source before reading prior examples or free-form style memory.
- If `Knowledge` exists, the draft should follow its policy wording and only then be polished to match the shop's tone.
- Prior reply examples are secondary style references, not the policy source of truth.
- Link the `Knowledge` row used for the inquiry in the inquiry record so the policy source is traceable.
- The reply output field is `Draft reply`.

Eligibility note:
- a greeting-only phrase is only actionable when it belongs to an active conversation that still needs a reply
- an information-only phrase is only actionable when it belongs to an active conversation that still needs a reply
- an `未返信` transaction is the only actionable scope for this skill
- canceled threads should be reported as historical matches only, not acted on

## Operating Rules

- The only operator-facing work surface is the Baserow `Tickets` table.
- Each run must also create one log row in Baserow table `916585` after the batch is complete.
- The log row must include a Markdown deliverable file listing all replied messages grouped by shop in table format.
- The Markdown deliverable must include the customer message arriving time for each replied thread.
- The Markdown table should use this column order:
  - `transaction_id`
  - `status`
  - `customer_message_arrived_at`
  - `buyer_message_id`
  - `buyer_message`
  - `reply_message_id`
  - `reply_message`
  - `replied_at`
- Do not use AI for routing when deterministic rules are sufficient.
- Keep `Reply Send State` limited to:
  - `Draft`
  - `Ready to Send`
  - `Sent`
- Treat `Reply Send State = Ready to Send` as the only send trigger.
- `Status` and `Needs Reply` are not send triggers.

### Status update rule

- Use `Status` only for case progress.
- Recommended updates:
  - `Open` when a ticket is first created or first upserted for human handling
  - `In Progress` while drafting, reviewing, or otherwise actively handling the case
- For `real_ticket` and `suspicious` cases:
  - `Closed Resolved` and `Closed Unresolved` are operator-only values
  - the agent must not assign either closed value
- For `greeting_only` and `information-only` cases:
  - set `Status = Closed Resolved` once the auto reply has been sent
- Do not change `Status` to control sending.
- Do not infer send readiness from `Status`; that remains the role of `Reply Send State`.

## End-of-Run Report

Every run must end with a short report that includes:

- run timestamp
- messages processed
- greeting-only count
- historical greeting-only matches, if any
- greeting-only message IDs and the reply sent
- real ticket count
- suspicious count
- tickets created or updated
- replies drafted
- replies sent
- errors or skipped items
- Baserow log row written to table `916585`
- Markdown deliverable written with customer message arriving time included

If no new messages are found, report that explicitly and still return a zero-count summary.

## Reference

See [report template](references/report_template.md) for the required output shape.

## Resources (optional)

Create only the resource directories this skill actually needs. Delete this section if no resources are required.

### scripts/
Executable code (Python/Bash/etc.) that can be run directly to perform specific operations.

**Examples from other skills:**
- PDF skill: `fill_fillable_fields.py`, `extract_form_field_info.py` - utilities for PDF manipulation
- DOCX skill: `document.py`, `utilities.py` - Python modules for document processing

**Appropriate for:** Python scripts, shell scripts, or any executable code that performs automation, data processing, or specific operations.

**Note:** Scripts may be executed without loading into context, but can still be read by Codex for patching or environment adjustments.

### references/
Documentation and reference material intended to be loaded into context to inform Codex's process and thinking.

**Examples from other skills:**
- Product management: `communication.md`, `context_building.md` - detailed workflow guides
- BigQuery: API reference documentation and query examples
- Finance: Schema documentation, company policies

**Appropriate for:** In-depth documentation, API references, database schemas, comprehensive guides, or any detailed information that Codex should reference while working.

### assets/
Files not intended to be loaded into context, but rather used within the output Codex produces.

**Examples from other skills:**
- Brand styling: PowerPoint template files (.pptx), logo files
- Frontend builder: HTML/React boilerplate project directories
- Typography: Font files (.ttf, .woff2)

**Appropriate for:** Templates, boilerplate code, document templates, images, icons, fonts, or any files meant to be copied or used in the final output.

---

**Not every skill requires all three types of resources.**
