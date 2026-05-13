---
name: baserow-schema-editor
description: Edit Baserow schema for Retailpulses databases by adding, renaming, or deleting fields after reading live schema and using JWT-based schema access.
---

# Baserow Schema Editor

Use this skill when the user wants to change Baserow structure, especially:

- add fields
- delete fields
- rename fields
- change field types
- change primary field
- review schema dependencies before a destructive edit

This skill is for schema changes only. Do not use it for normal row/data writes.

## Core Rules

- Read the live schema first.
- Do not assume field names or field types.
- Use `user_field_names=true` for readable field names.
- Schema edits require a JWT user token, not a database token.
- Database tokens are for row/data operations only.
- Use a Baserow service account with Builder or Admin rights on the target database.
- If JWT or permissions are missing, stop and ask the user.

## Recommended Workflow

1. Confirm the target database and table.
2. Read the live table schema and list all current fields.
3. Compare requested changes against current fields.
4. Check for dependencies before destructive actions.
5. Get explicit confirmation before deleting or changing a field type.
6. Apply schema changes through the Baserow schema API.
7. Re-read the schema after the change.
8. Verify the final field list matches the request.

## Safety Checks

- Before deleting a field, inspect whether it is used by formulas, lookups, rollups, views, filters, or automations.
- Before changing a field type, confirm whether existing data can be preserved.
- Before renaming a field, confirm whether downstream code depends on the old label.
- Prefer additive changes over destructive changes.

## Common Patterns

- For a new text field, create a `text` field.
- For longer copy fields, create a `long_text` field.
- For numeric quantity fields, create a `number` field.
- For yes/no flags, create a `boolean` field.
- For date values, create a `date` field only if the value is truly date-only.

## What To Report Back

After editing schema, report:

- fields added, renamed, changed, or deleted
- target table id
- auth method used
- any dependencies or risks found
- whether the live schema re-check matched the requested change

## Reference

See `Retailpulses Baserow access SOP.md` in `/Users/user/Documents/march 2026/Baserow ERP/` for the access model and JWT requirement.
