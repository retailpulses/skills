---
name: giga-resource-pack-copywriting
description: Generate Japanese Rakuten, Amazon, and Mercari copy from a Giga Item Code by looking up the resource pack in Baserow table 912520, applying platform strategy records from table 912423, and writing outputs to table 912536. Also supports explicit ZIP-input fallback when the user provides a local pack.
---

# Giga Resource Pack Copywriting

Use this skill when the user wants `Item Code -> resource pack lookup -> marketplace copywriting`.

Supported outputs:

- `Rakuten`
- `Amazon`
- `Mercari`

Primary mode:

- input is `Item Code`
- look up source pack-derived product info in Baserow table `912520`
- apply platform copy strategy records from Baserow table `912423`
- write final copy to Baserow table `912536`
- facts first, copy second
- parent-level copy by default
- no market research unless the user explicitly asks

Fallback mode:

- if the user explicitly provides a local ZIP instead of an Item Code, use the ZIP directly
- still prefer writing final outputs to Baserow if the task asks for it

## Required tables

- Resource-pack lookup: `https://baserow.io/database/393156/table/912520/`
- Platform strategies: `https://baserow.io/database/393156/table/912423`
- Output table: `https://baserow.io/database/393156/table/912536`

## Baserow Access

- Authenticate row operations with `Authorization: Token <database token>`.
- Read rows with `user_field_names=true` so the live field labels are usable as keys.
- Page through tables with `size=200&page=<n>` when reading more than one screen of data.
- Inspect the live schema first if any field name or table role may have drifted.
- Treat `912520`, `912423`, and `912536` as live data tables, not static snapshots.
- Use `912520` and `912423` as read sources, and `912536` as the append-only output table.
- When writing to `912536`, create new rows only; do not update existing rows unless the user explicitly asks for a rewrite.
- Never assume a field exists just because the skill previously used it; confirm it in the live schema first.

## Live Schema Confirmed

Confirmed on `2026-04-01 JST` via Baserow API.

- `912520` is the item facts table.
- `912423` is the platform strategy table.
- `912536` is the output table, one row per `Item Code + Platform`.

Useful fields:

- `912520`: `Item Code`, `Product Name`, `Package Size-Length (cm)`, `Package Size-Width (cm)`, `Package Size-Height (cm)`, `Package Size-Weight (kg)`, `Description`, `Product Features 1..10`, `Product Main Image`, `Product Images (exclude main)1..26`, `Additional Images`, `Certification Documents 1`, `Certification Documents 2`, `Assembly Instructions`, `Normalized descriptions`, `Normalized Product Name`, `If Home & Kitchen`
- `912423`: `Name`, `Contents`, `Active`, `Platform`, `Version ID`
- `912536`: `Title`, `Description Text`, `Active`, `Item Code`, `Version ID`, `Platform`, `Description html`, `Listing status`, `CSV exported on`

## Workflow

### Script Runner (for skill-to-skill invocation)

Use this runner when another skill needs to auto-generate missing copywriting rows:

```bash
python3 scripts/generate_copywriting_rows.py \
  --item-codes "$ITEM_CODES_OR_FILE" \
  --platform mercari
```

- Creates rows in table `912536` with `Platform=Mercari`, `Active=true`.
- Default behavior is create-only-missing (skips Item Codes that already have Mercari copy).

### 1. Resolve the input

- default assumption: the user gives an `Item Code`
- inspect `912520`, find the exact row, and use the most complete match if duplicates exist
- if ambiguity could target the wrong product, stop and ask the user
- use `Product Name`, `Normalized Product Name`, `Description`, `Product Features 1..10`, `Package Size-*`, `Product Main Image`, `Product Images (exclude main)1..26`, `Additional Images`, `Assembly Instructions`, and `If Home & Kitchen` as the live mapping set

### 2. Source completeness rules

- if the user did not provide a ZIP, work from live Baserow fields only
- if raw ZIP / HTML files are missing, treat that as normal
- omit unsupported returns, warranty, weight, assembly, or fit details rather than stating they are missing
- if something is inferred from images or context, mark it `推定`

### 3. Load platform copy strategies

- inspect `912423`
- load active rows for `generic`, `Rakuten`, `Amazon`, and `Mercari`
- use source facts over strategy guidance, and marketplace policy over strategy guidance
- persist strategy row ids or `Version ID` values when useful

### 4. Build a facts layer first

- capture parent SKU, child SKU, product name, type, use case, color, material, dimensions, weight, quantity, assembly, packaging, image URLs, shared selling points, strategy rows used, missing fields, and inferred fields
- do not write copy before the facts layer is stable
- keep only parent-level shared claims for multi-variant packs

### 5. Generate platform outputs

- create facts, `Rakuten` HTML, `Rakuten` plain text, `Amazon` structured text, and `Mercari` simplified text
- ground every output in the source pack, the facts layer, and the active strategy row

## Platform Baseline Rules

- Rakuten: output HTML + text, keep a complete marketplace description, and include specs, usage notes, shipping, and sourced warranty / returns only when present.
- Amazon: output non-HTML, exactly 5 bullets, and a fuller description body; keep `Description 1` to bullets only and `Description 2` to the main body.
- Mercari: start from the Rakuten text version, apply the active Mercari prefix / appendix, and strip strategy-control labels before final output.
- Mercari title rules:
  - remove `元SKU` / `元SKU:` prefixes from the title
  - enrich the title with factual search keywords from the product pack when space allows, especially `Item Code`-adjacent facts, size, structure, material, color, and category terms
  - keep the title readable and compact; prefer search relevance over slogan-like wording
  - do not repeat the same fact twice in different forms
  - keep the final title within the platform-safe length and trim secondary descriptors first
- Mercari description cleanup:
  - derive the body from the Rakuten-style plain text structure
  - keep exactly one blank line between top-level sections
  - remove blank lines inside a section
  - collapse repeated blank lines and trim whitespace on every line
  - remove stray control characters or OCR noise such as standalone `n` heading fragments
  - strip control labels such as `Title`, `Dimensions & Details`, `Attention`, `Features`, and raw `SKU` markers even when they are attached to another heading line
  - keep section headings and bullet structure readable

## Writing to Baserow

- Inspect `912536` before writing.
- Treat it as append-only: one new row per `Item Code + Platform`.
- Use `Item Code`, `Platform`, `Title`, `Description Text`, `Description html`, and `Listing status=Drafted` as the core payload.
- `Description html` is Rakuten only; leave it empty for Amazon and Mercari.
- Leave `Active` untouched and do not update existing rows.
- If a spec is missing, omit it instead of adding a missing-data disclaimer.

## Local artifacts

- Use local temporary files only when needed to:
  - download the source pack
  - unpack the pack
  - inspect workbook or HTML files
  - stage drafts before writing to Baserow

Only create durable local or OneDrive copies if:

- the user explicitly asks for file outputs, or
- the workflow requires an archive in addition to Baserow

## Image Use

Image analysis is optional enhancement, not a blocker.

Use images only to conservatively support:

- style judgment
- visible structure / silhouette
- surface or material feel

If image-based conclusions are uncertain, omit them or mark them as `推定`.

Do not make main-image generation part of this skill.

## Quality Bar

- confirm the correct `Item Code` row was used from table `912520`
- confirm the relevant strategy rows from table `912423` were applied
- confirm all outputs share the same facts layer
- confirm Rakuten has HTML and text
- confirm Amazon has exactly 5 bullets and no HTML
- confirm Mercari is shorter and simpler than Rakuten
- confirm missing fields are omitted, not hallucinated
- confirm the final output was written to table `912536`

## Output Style

When executing this skill, prefer concise delivery:

- write the copy directly to Baserow when that is the requested workflow
- keep explanations short
- state clearly what was missing, inferred, or skipped
