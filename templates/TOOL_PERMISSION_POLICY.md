# TOOL_PERMISSION_POLICY.md

# Tool Permission Policy

This file defines the practical permission boundaries for agents.

`AGENTS.md` controls behavior.  
`TASK_BRIEF_TEMPLATE.md` controls the task contract.  
`TOOL_PERMISSION_POLICY.md` controls what agents are actually allowed to do with tools, credentials, APIs, files, and environments.

The key principle:

> Do not rely only on prompt instructions. Use environment separation, dry-run defaults, credential control, and explicit confirmation to prevent real damage.

---

## 1. Permission Philosophy

Agents should operate with the least privilege necessary.

Default mode:

- Read is allowed when required for the task.
- Drafting is allowed.
- Local file creation is allowed.
- Dry-run is preferred.
- Production write actions are blocked unless explicitly authorized.

The Manager Agent must treat tool access as risk-bearing.

---

## 2. Environment Separation

Use separate environments whenever possible:

- Local
- Development
- Staging
- Production

Agents should default to local or development environments.

Production access should be exceptional, explicit, and logged.

### Recommended Environment Variables

```bash
APP_ENV=development
DRY_RUN=true
ALLOW_PRODUCTION_WRITE=false
ALLOW_CUSTOMER_SEND=false
ALLOW_MARKETPLACE_PUBLISH=false
ALLOW_DELETE=false
```

For production:

```bash
APP_ENV=production
DRY_RUN=false
ALLOW_PRODUCTION_WRITE=true
```

Production settings should only be enabled after explicit user confirmation.

---

## 3. Default Tool Permission Levels

### Level 0: No External Tools

Allowed:

- Reasoning.
- Planning.
- Drafting.
- Reviewing user-provided text.

Not allowed:

- File modification.
- API calls.
- External network actions.

Use for sensitive planning or early discussion.

---

### Level 1: Local Draft Tools

Allowed:

- Create local files.
- Edit local draft files.
- Generate Markdown, CSV, JSON, or code drafts.
- Run local validation scripts.
- Perform dry-run operations.

Not allowed:

- Production API calls.
- Customer messages.
- Marketplace publishing.
- Live database writes.
- Deletion of important files.

This should be the default working level for most agent tasks.

---

### Level 2: Development System Access

Allowed:

- Read and write development databases.
- Call development APIs.
- Deploy to development environments.
- Test workflows using test data.

Not allowed:

- Production changes.
- Customer-facing messages.
- Marketplace publishing.
- Official submissions.

Use for implementation and testing.

---

### Level 3: Controlled Production Read

Allowed:

- Read production data required for the task.
- Export reports.
- Validate production status.

Not allowed:

- Production writes.
- Customer messages.
- Publishing.
- Deleting.
- Deploying production changes.

Use when real data is needed, but changes are not authorized.

---

### Level 4: Controlled Production Write

Allowed only after explicit confirmation.

May include:

- Updating production records.
- Uploading production files.
- Publishing marketplace listings.
- Sending customer messages.
- Deploying production changes.

Requirements:

- Clear action list.
- User confirmation.
- Dry-run result reviewed first when possible.
- Backup or rollback plan when relevant.
- Execution log.

---

### Level 5: Destructive or Official Actions

Allowed only with strong explicit confirmation.

Examples:

- Deleting production data.
- Bulk overwrites.
- Financial actions.
- Legal, tax, visa, or compliance submissions.
- Sending large batches of customer communications.
- Irreversible marketplace actions.

Requirements:

- Written confirmation from user.
- Exact scope.
- Backup plan.
- Rollback plan if possible.
- Final pre-execution checklist.
- Post-execution report.

---

## 4. Tool Action Matrix

| Action | Default Permission | Confirmation Required | Notes |
|---|---:|---:|---|
| Draft Markdown | Allowed | No | Local only |
| Create local CSV | Allowed | No | Unless overwriting important file |
| Generate API payload draft | Allowed | No | Do not send it |
| Dry-run script | Allowed | Usually no | Must be non-destructive |
| Read dev database | Allowed if needed | No | Avoid unnecessary access |
| Write dev database | Allowed if in task scope | Sometimes | Use test data |
| Read production database | Restricted | Yes if sensitive | Prefer narrow read |
| Write production database | Blocked by default | Yes | Require exact scope |
| Delete records | Blocked | Yes | High risk |
| Send email/customer message | Blocked | Yes | Must review message first |
| Publish marketplace listing | Blocked | Yes | Must review final listing first |
| Upload files to production | Blocked | Yes | Confirm destination |
| Deploy to development | Allowed if in task scope | Sometimes | Report result |
| Deploy to production | Blocked | Yes | Require rollback plan |
| Change credentials/secrets | Blocked | Yes | Avoid exposing secrets |
| Submit official forms | Blocked | Yes | High-risk compliance action |

---

## 5. Credential Handling Rules

Agents must not expose credentials in logs, reports, screenshots, or final answers.

### 5.1 Do Not Store Secrets in Markdown

Do not put API keys, passwords, OAuth tokens, secret keys, or private certificates in Markdown files.

Use environment variables or secret managers.

Examples:

```bash
BASEROW_TOKEN=***
CLOUDFLARE_API_TOKEN=***
RAKUTEN_API_SECRET=***
```

### 5.2 Credential Usage

Before using credentials in a new environment, the Manager Agent must confirm:

- Which credential is required.
- What system it will access.
- Whether the target is dev or production.
- Whether the action is read-only or write.

### 5.3 Credential Rotation

If a secret is exposed, the recommended action is to rotate it immediately.

---

## 6. Dry-Run First Rule

For any action that may affect external systems, agents should produce a dry-run first whenever possible.

Dry-run output should include:

```md
## Dry-Run Result

- Target system:
- Intended action:
- Number of records affected:
- Example changes:
- Risks:
- Confirmation needed:
```

Only after user confirmation should the action be executed for real.

---

## 7. Production Write Checklist

Before production write actions, complete this checklist:

- [ ] User explicitly authorized Execution Mode.
- [ ] Target environment is confirmed as production.
- [ ] Exact action is defined.
- [ ] Affected records/files/listings are identified.
- [ ] Dry-run or preview was provided when possible.
- [ ] Backup or rollback plan exists when relevant.
- [ ] Credentials are available through secure environment variables.
- [ ] No secrets are shown in output.
- [ ] The Manager Agent has summarized the final action before execution.

---

## 8. Customer Communication Rules

Agents must not send customer-facing messages without confirmation.

Allowed in Preparation Mode:

- Draft customer message.
- Translate message.
- Improve tone.
- Create response options.

Blocked without confirmation:

- Sending email.
- Sending marketplace inquiry reply.
- Sending chat message.
- Bulk messaging customers.

Before sending, confirm:

- Recipient.
- Channel.
- Message content.
- Timing.
- Whether this is a one-off or bulk send.

---

## 9. Marketplace Operation Rules

Marketplace operations are high-risk.

Blocked without confirmation:

- Listing publish.
- Listing unpublish.
- Price update.
- Inventory update.
- Bulk upload.
- Customer reply.
- Order operation.
- Cancellation or refund action.

Preparation Mode allows:

- CSV generation.
- Listing draft generation.
- Field validation.
- Image URL checking.
- Policy risk review.
- Upload plan.

Execution requires explicit user confirmation.

---

## 10. Database Operation Rules

### 10.1 Read Operations

Read only the minimum data required.

When reading sensitive or production data, state why it is needed.

### 10.2 Write Operations

Production writes require confirmation.

Bulk writes require:

- Dry-run.
- Count of affected records.
- Sample before/after.
- Rollback strategy if possible.

### 10.3 Delete Operations

Delete operations are high-risk.

Prefer soft delete, archive, or status change when possible.

Hard delete requires strong confirmation.

---

## 11. File System Rules

Allowed by default:

- Create new draft files.
- Create reports.
- Create generated output files.
- Edit files clearly within task scope.

Require confirmation:

- Overwriting important files.
- Deleting files.
- Moving large directories.
- Changing project-wide configuration.
- Modifying credential files.

Recommended generated file naming:

```txt
output/YYYYMMDD_task-name_draft.ext
output/YYYYMMDD_task-name_report.md
output/YYYYMMDD_task-name_dry-run.json
```

---

## 12. Logging and Audit Trail

For medium-risk or high-risk work, keep an execution log:

```md
## Execution Log

- Timestamp:
- Agent / model:
- Task:
- Environment:
- Action:
- Files touched:
- External systems touched:
- Result:
- Errors:
- Rollback available:
```

For low-risk drafting tasks, a full log is usually unnecessary.

---

## 13. Recommended Prompt for Agents

Use this instruction at the start of a task:

```txt
Read AGENTS.md, TASK_BRIEF_TEMPLATE.md, and TOOL_PERMISSION_POLICY.md first.

Act as the Manager Agent.

Default to Preparation Mode.
Do not perform live external actions unless explicitly authorized.
Use subagents only when useful.
Maintain working state for long tasks.
Report risks and ask for confirmation before high-risk actions.
```

---

## 14. Recommended Repository Placement

Suggested minimal structure:

```txt
project-root/
├── AGENTS.md
├── TASK_BRIEF_TEMPLATE.md
├── TOOL_PERMISSION_POLICY.md
├── tasks/
│   └── current-task.md
├── output/
└── scripts/
```

Suggested expanded structure:

```txt
project-root/
├── AGENTS.md
├── TASK_BRIEF_TEMPLATE.md
├── TOOL_PERMISSION_POLICY.md
├── context/
│   ├── BUSINESS_CONTEXT.md
│   ├── MARKETPLACE_RULES.md
│   ├── SECURITY_RULES.md
│   └── DATA_MODEL_OVERVIEW.md
├── agents/
│   ├── manager.md
│   ├── rakuten_listing_agent.md
│   ├── mercari_cs_agent.md
│   ├── product_research_agent.md
│   └── data_validation_agent.md
├── tasks/
├── output/
└── scripts/
```

---

## 15. Critical Reminder

Prompt rules reduce risk, but they are not enough.

Reliable agent operations require:

```txt
Rules file + Task brief + Tool permission control + Environment separation + Human confirmation
```

Do not give agents production credentials unless the task truly requires it.
