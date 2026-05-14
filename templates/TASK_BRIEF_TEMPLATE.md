# TASK_BRIEF_TEMPLATE.md

# Task Brief Template

Use this file for each concrete task.

`AGENTS.md` defines the general Manager Agent behavior. This file defines the specific objective, scope, boundaries, output, and confirmation points for one task.

A task should not begin until the Manager Agent understands this brief or has made reasonable assumptions and clearly stated them.

---

## 1. Task Name

<!-- Example: Prepare Rakuten Listing CSV for Selected Products -->


---

## 2. Objective

<!-- What is the business, product, or operational goal of this task? -->


---

## 3. Background / Context

<!-- Relevant context, links, files, systems, business rules, or prior decisions. -->


---

## 4. Scope

### 4.1 Included

The agent may do the following:

- 
- 
- 

### 4.2 Excluded

The agent must not do the following:

- 
- 
- 

---

## 5. Working Mode

Select one:

- [ ] Preparation Mode only
- [ ] Execution Mode allowed after explicit confirmation
- [ ] Execution Mode already authorized for the specific actions listed below

### Authorized Execution Actions

<!-- Leave blank unless explicitly authorized. -->

- 

---

## 6. Inputs

### 6.1 Files

- 

### 6.2 Data Sources

- 

### 6.3 Credentials / Secrets

Do not paste credentials directly into this file unless the environment is secure and the user has explicitly approved it.

Required credentials or environment variables:

- 

### 6.4 External Systems

- 

---

## 7. Expected Outputs

The final deliverables should include:

- 
- 
- 

Examples:

- Markdown report.
- CSV draft file.
- Missing data report.
- Risk checklist.
- API payload draft.
- Implementation plan.
- Code diff.
- Test result summary.

---

## 8. Success Criteria / Definition of Done

The task is complete when:

- [ ] 
- [ ] 
- [ ] 

---

## 9. Quality Criteria

The output should satisfy the following quality standards:

- Accurate.
- Structured.
- Directly usable.
- No hidden assumptions.
- Risks clearly identified.
- Missing information clearly reported.
- No unauthorized live actions.

Additional task-specific quality criteria:

- 
- 
- 

---

## 10. Constraints

### 10.1 Technical Constraints

- 

### 10.2 Business Constraints

- 

### 10.3 Marketplace / Platform Constraints

- 

### 10.4 Legal / Compliance Constraints

- 

---

## 11. Risk Checklist

The Manager Agent should check the following risks before finalizing the task:

- [ ] Scope creep
- [ ] Data loss
- [ ] Production impact
- [ ] Credential exposure
- [ ] Customer communication risk
- [ ] Marketplace policy risk
- [ ] Legal / compliance risk
- [ ] Operational maintenance burden
- [ ] Cost increase
- [ ] Vendor lock-in
- [ ] Future scalability limitation

Task-specific risks:

- 
- 
- 

---

## 12. Subagent Plan

Use subagents only when useful.

### Suggested Subagents

| Subagent | Objective | Input | Expected Output | Risk Level |
|---|---|---|---|---|
|  |  |  |  |  |
|  |  |  |  |  |

### Subagent Rules

Subagents must not:

- Execute production actions.
- Change task scope.
- Make final decisions independently.
- Send external communications.
- Modify live data.

All subagent outputs must return to the Manager Agent for review and integration.

---

## 13. Confirmation Required

The Manager Agent must ask the user before:

- 
- 
- 

Default confirmation triggers:

- Uploading.
- Publishing.
- Sending.
- Deleting.
- Deploying.
- Updating production.
- Submitting official forms.
- Using credentials in a new environment.

---

## 14. Progress Reporting

For long tasks, use this format:

```md
## Progress Update

- Completed:
- Working On:
- Blockers:
- Next:
```

Report meaningful progress only.

---

## 15. Working State

The Manager Agent should maintain the current task state:

```md
## Working State

### Objective
-

### Scope
-

### Completed
-

### In Progress
-

### Pending
-

### Blockers
-

### Decisions Made
-

### Assumptions
-

### Risks
-

### User Confirmation Needed
-

### Next Actions
-
```

---

## 16. Handoff Summary

If the task is paused, interrupted, or handed to another model, produce:

```md
## Handoff Summary

### Original Objective
-

### Current Status
-

### Important Decisions
-

### Files / Systems Touched
-

### Open Questions
-

### Recommended Next Step
-
```

---

## 17. Notes

<!-- Optional notes for the Manager Agent. -->


