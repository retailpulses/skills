---
name: baserow-schema-editor
description: USE baserow-database-manager for ALL schema editing — this skill has been merged into baserow-database-manager.
---

# Baserow Schema Editor (Merged)

**This skill has been consolidated into `baserow-database-manager`.**

The `baserow-database-manager` skill covers all schema editing functionality previously documented here:

- Reading live schema and listing fields
- Adding, renaming, and deleting fields
- Changing field types and primary fields
- Reviewing schema dependencies before destructive edits
- Common field type patterns (text, long_text, number, boolean, date, link_row, single_select)

It additionally covers full CRUD row operations, batch endpoints (PATCH/CREATE/DELETE), and operational procedures that this standalone skill lacked.

**Next action:** Use `baserow-database-manager` instead. All schema operations — reading live schema, adding/deleting/renaming fields, changing field types — are documented there with the same JWT auth and safety-check requirements.
