# Baserow → Supabase Skills Migration Playbook

**Created:** 2026-07-18
**Governance ref:** `rp-governance-kit` v1.5.0 (`DATABASE_GOVERNANCE.md`)
**Target:** 14 skills, 4 phases
**Runtime:** ~4-6 sessions (estimated)

---

## Pre-Flight

### Session 0 — Audit & Baseline (this session)

- [ ] Confirm `supabase` CLI installed and version recorded
- [ ] Confirm RPagentOS repo at `/Users/user/Documents/Retailpulses/20_REPOS/RPagentOS`
- [ ] Confirm governance kit at `/Users/user/Documents/Retailpulses/20_REPOS/rp-governance-kit`
- [ ] Snapshot current state: `git -C skills log --all --oneline -5`
- [ ] Read current Supabase schema: `supabase db dump --linked` from RPagentOS (read-only audit)
- [ ] Inventory all Baserow tables referenced by skills and map to Supabase objects

### Baserow → Supabase table mapping

| Baserow Table ID | Baserow Name | Supabase Equivalent | Status |
|-----------------|--------------|---------------------|--------|
| 886994 | Products | `baserow_886994_compat_vw` (view over `product_variants` + `product_commercials`) | ✅ Exists |
| 912520 | Resource Packs (Giga) | **None yet** | 🔴 Needs creation |
| 912423 | Platform Copy Strategies | **None yet** | 🔴 Needs creation |
| 912536 | Copywriting Outputs | **None yet** | 🔴 Needs creation |
| 938452 | Mercari Batch Update Log | **None yet** | 🔴 Needs creation |
| 886975 | Mercari Inquiries | **None yet** | 🔴 Needs creation |
| 914491 | (timesale related) | **None yet** | 🔴 Needs creation |
| — | Amazon Listings | **None yet** | 🔴 Needs creation |

---

## Phase 0 — Retire Baserow-Native Skills

**Goal:** Delete 2 skills that exist only to manage Baserow. No governance overhead.

### Execution (1 session, ~5 min)

```
Step 0.1  Delete baserow-database-manager/
          rm -rf skills/baserow-database-manager

Step 0.2  Delete baserow-schema-editor/
          rm -rf skills/baserow-schema-editor

Step 0.3  Commit
          git add -A
          git commit -m "chore: retire baserow-native skills (baserow-database-manager, baserow-schema-editor)

          Baserow is being retired. These skills managed Baserow schema/API
          and have no Supabase equivalent.

          Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Gate check:** ✅ No governance registrations needed — these skills touched only Baserow APIs, never Supabase.

---

## Phase 1 — Complete In-Progress Migrations

**Goal:** Finish the 2 skills that already have Supabase code paths but carry legacy Baserow cruft.

### Execution (1 session, ~30 min)

#### Step 1.1 — sync-giga-saved-products

```
1.1a  Make Supabase default
      Edit SKILL.md: change "Set USE_SUPABASE=true to use the new Supabase backend.
      The default (USE_SUPABASE=false) uses the legacy Baserow 886994 path."
      → "Default backend is Supabase. Legacy Baserow path is removed."

1.1b  Delete legacy Baserow scripts
      rm scripts/sync.py        # Baserow 886994 sync
      rm scripts/backfill.py    # Baserow PATCH backfill

1.1c  Update SKILL.md
      - Strip all Baserow API references
      - Update description to say "Supabase product_variants + product_commercials"
      - Update credential requirements: BASEROW_TOKEN → SUPABASE_SERVICE_ROLE_KEY

1.1d  Update agents/openai.yaml
      - Change short_description to reference Supabase, not Baserow
```

#### Step 1.2 — mercari-csv-listing

```
1.2a  Strip Baserow references from SKILL.md
      - Remove references to api.baserow.io
      - Remove references to BASEROW_TOKEN
      - Update data source description to Supabase baserow_886994_compat_vw

1.2b  Clean up build_mercari_listing_csv.py
      - Remove --baserow-workers flag (already ignored)
      - Remove Baserow URL references in comments

1.2c  Update README.md
      - Change data source from Baserow to Supabase

1.2d  Update agents/openai.yaml
      - Change short_description to reference Supabase
```

#### Step 1.3 — Commit Phase 1

```
git add -A
git commit -m "chore: complete Baserow→Supabase migration for sync-giga-saved-products and mercari-csv-listing

- sync-giga-saved-products: Supabase is now default, legacy Baserow scripts removed
- mercari-csv-listing: Baserow references stripped, Supabase is the only data source

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Governance for Phase 1

Both skills are already registered in the governance kit:
- `DATABASE_OWNERSHIP.yaml`: ✅ `retailpulses/skills:sync-giga-saved-products`, `retailpulses/skills:mercari-csv-listing`
- `DATABASE_ACCESS_POLICY.yaml`: ✅ Both have `internal_api` entries
- `DATABASE_CAPABILITIES.yaml`: ✅ Both have capability declarations

**Action needed:** Add workload declarations to `DATABASE_WORKLOADS.yaml`:
- `skills_sync_giga_products` (write, manual trigger, ~100-500 rows/run)
- `skills_mercari_csv_listing_read` (read-only, manual trigger)

---

## Phase 2 — Migrate 886994-Reader Skills (No New Schema)

**Goal:** Migrate 3 skills that read from what was Baserow `Products` (886994). They can consume the existing `baserow_886994_compat_vw` view. No new Supabase tables needed.

### Execution (~1 session per skill, ~2-3 hours total)

#### Step 2.1 — mercari-category-id

```
2.1a  Rewrite data access layer
      Create scripts/supabase_client.py with:
        - fetch_products_without_category() → queries baserow_886994_compat_vw
          WHERE "Mercari category ID" IS NULL
        - update_mercari_category_id(item_code, category_id) → PostgREST PATCH
        - Uses SUPABASE_URL + SUPABASE_ANON_KEY or service_role key

2.1b  Update SKILL.md
      - Replace all Baserow API references with Supabase PostgREST
      - Update credential requirements
      - Update workflow to reference baserow_886994_compat_vw

2.1c  Update agents/openai.yaml
```

#### Step 2.2 — mercari-listing-id-sync

```
2.2a  Rewrite data access
      Create scripts/supabase_client.py with:
        - fetch_products_without_mercari_id(shop_number) → queries
          baserow_886994_compat_vw WHERE "Mercari ShopX Product ID" IS NULL
        - write_mercari_product_id(item_code, shop_number, product_id) →
          PostgREST PATCH to platform_listings

2.2b  Update SKILL.md + references/*.md
      - Replace Baserow API examples with Supabase PostgREST
      - Update PRODUCTS_TABLE_FIELDS.md to describe Supabase columns
```

#### Step 2.3 — mercari-add-variant

```
2.3a  Rewrite data access
      Create scripts/supabase_client.py with:
        - fetch_spu1_group(spu1_code) → queries baserow_886994_compat_vw
          WHERE "SPU1" = spu1_code
        - create_platform_listing(...) → PostgREST INSERT to platform_listings
        - Uses Mercari GraphQL for actual listing creation (unchanged)

2.3b  Update SKILL.md + references/rollback.md
      - Replace Baserow references
```

#### Step 2.4 — Governance registration for Phase 2

For each of the 3 skills, submit PR to `rp-governance-kit`:

```
rp-governance-kit PR: "Register 3 skills as product_catalog consumers"

DATABASE_OWNERSHIP.yaml:
  - Add retailpulses/skills:mercari-category-id to product_catalog.consumers
  - Add retailpulses/skills:mercari-listing-id-sync to product_catalog.consumers
  - Add retailpulses/skills:mercari-add-variant to product_catalog.consumers

DATABASE_ACCESS_POLICY.yaml:
  - Add entry for each with internal_api, write_scoped credential class

DATABASE_CAPABILITIES.yaml:
  - Add entry for each: read=true, write=true, schema_change=false

DATABASE_WORKLOADS.yaml:
  - Add workload entry for each (all write, manual trigger, <500 rows)
```

**Gate check before proceeding to Phase 3:**
- [ ] Governance PR merged
- [ ] Credentials issued (per-skill PostgREST keys)
- [ ] Dry-run: each skill can read from `baserow_886994_compat_vw`

---

## Phase 3 — Create New Supabase Tables + Migrate Write-Heavy Skills

**Goal:** 4 skills that write to Baserow tables with NO existing Supabase equivalent. New tables must be created **in RPagentOS** (the `product_catalog` domain owner).

### Phase 3a — RPagentOS: Create new tables (1 session)

Create migrations in `RPagentOS/supabase/migrations/`:

```sql
-- Migration: 20260718NNNN01_create_resource_packs.sql
-- Domain: product_catalog
-- Owner: retailpulses/RPagentOS
-- Affected: resource_packs, platform_copy_strategies, copywriting_outputs
-- Change class: additive
-- Hosted write required: yes
-- Consumers: retailpulses/skills:giga-resource-pack-copywriting

CREATE TABLE resource_packs (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  item_code TEXT NOT NULL UNIQUE,
  pack_data JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE platform_copy_strategies (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  platform TEXT NOT NULL,  -- 'rakuten', 'amazon', 'mercari'
  strategy_config JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE copywriting_outputs (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  item_code TEXT NOT NULL,
  platform TEXT NOT NULL,
  copy_text TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS (worker_only access class)
ALTER TABLE resource_packs ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_copy_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE copywriting_outputs ENABLE ROW LEVEL SECURITY;
```

```sql
-- Migration: 20260718NNNN02_create_mercari_batch_update_log.sql
-- Domain: product_catalog
-- Owner: retailpulses/RPagentOS
-- Affected: mercari_batch_update_log
-- Change class: additive
-- Hosted write required: yes
-- Consumers: retailpulses/skills:mercari-batch-update

CREATE TABLE mercari_batch_update_log (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  listing_id TEXT NOT NULL,
  shop TEXT NOT NULL,
  update_type TEXT NOT NULL,  -- 'price', 'stock', 'title', etc.
  old_value TEXT,
  new_value TEXT,
  success BOOLEAN DEFAULT false,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE mercari_batch_update_log ENABLE ROW LEVEL SECURITY;
```

```sql
-- Migration: 20260718NNNN03_create_mercari_inquiries.sql
-- Domain: product_catalog
-- Owner: retailpulses/RPagentOS
-- Affected: mercari_inquiries
-- Change class: additive
-- Hosted write required: yes
-- Consumers: retailpulses/skills:mercari-inquiry-follow-up

CREATE TABLE mercari_inquiries (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  mercari_inquiry_id TEXT,
  shop TEXT NOT NULL,
  customer_name TEXT,
  item_code TEXT,
  status TEXT DEFAULT 'open',
  last_message_at TIMESTAMPTZ,
  follow_up_sent_at TIMESTAMPTZ,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE mercari_inquiries ENABLE ROW LEVEL SECURITY;
```

```sql
-- Migration: 20260718NNNN04_create_amazon_listings.sql
-- Domain: product_catalog
-- Owner: retailpulses/RPagentOS
-- Affected: amazon_listings
-- Change class: additive
-- Hosted write required: yes
-- Consumers: retailpulses/skills:amazon-inventory-flatfile

CREATE TABLE amazon_listings (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  item_code TEXT NOT NULL,
  asin TEXT,
  sku TEXT,
  price INTEGER,
  quantity INTEGER,
  fulfillment_channel TEXT DEFAULT 'DEFAULT',
  last_synced_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE amazon_listings ENABLE ROW LEVEL SECURITY;
```

### Phase 3b — Rewrite 4 skill scripts (1 session per skill)

```
3b.1  amazon-inventory-flatfile
      - Rewrite sync_baserow_inventory.py → sync_supabase_inventory.py
        (read from baserow_886994_compat_vw, write to amazon_listings)
      - Rewrite build_inventory_flatfile.py to read from Supabase
      - Delete sync_baserow_inventory.py
      - Update SKILL.md

3b.2  giga-resource-pack-copywriting
      - Rewrite generate_copywriting_rows.py to use Supabase PostgREST
        (read resource_packs + platform_copy_strategies, write copywriting_outputs)
      - Update SKILL.md + agents/openai.yaml

3b.3  mercari-batch-update
      - Rewrite mercari_batch_update.py to use Supabase PostgREST
      - Replace baserow_client with supabase-py or httpx (PostgREST)
      - Write results to mercari_batch_update_log
      - Update SKILL.md + references/csv-columns.md

3b.4  mercari-inquiry-follow-up
      - Rewrite baserow_inquiries.mjs → supabase_inquiries.mjs
        (PostgREST queries to mercari_inquiries table)
      - Update SKILL.md + CHANGELOG.md
```

### Phase 3c — Governance registration (performed per skill after rewrite)

For each of the 4 skills:

```
1. PR to rp-governance-kit:
   - DATABASE_OWNERSHIP.yaml: add consumer
   - DATABASE_ACCESS_POLICY.yaml: add access policy
   - DATABASE_CAPABILITIES.yaml: add capability (read+write)
   - DATABASE_WORKLOADS.yaml: add workload with FULL safety_profile
     (these are write-heavy, all need extended profile)

2. Workload declaration checklist (DATABASE_GOVERNANCE.md §13.2):
   - [ ] Category (imports/syncs/scheduled_jobs)
   - [ ] Affected domains
   - [ ] Expected row volume
   - [ ] Concurrency limit
   - [ ] Statement timeout
   - [ ] Retry strategy
   - [ ] Kill switch
   - [ ] Dry-run evidence
   - [ ] Monitoring plan

3. Rollout gates (§13.13):
   - [ ] Zero-write dry-run
   - [ ] Bounded canary (≤100 rows)
   - [ ] Manual full run
   - [ ] 2 healthy scheduled cycles
```

**Gate check before Phase 4:**
- [ ] All 4 RPagentOS migrations applied to production
- [ ] All 4 governance PRs merged
- [ ] All 4 skills tested with dry-run against Supabase
- [ ] PostgREST credentials issued for each skill

---

## Phase 4 — Cleanup Remaining References

**Goal:** Update 3 skills with indirect/reference-only Baserow mentions.

### Execution (~30 min)

```
4.1  gigab2b-workflow
     - Update SKILL.md: replace "Baserow table 886994" with
       "Supabase product_variants + product_commercials (via baserow_886994_compat_vw)"
     - Update agents/openai.yaml short_description
     - No code changes needed (engine is sync-giga-saved-products, already migrated)

4.2  mercari-timesale-csv
     - If the Supabase tables from Phase 3 cover timesale data, update references
     - If not, add note: "Timesale data sources pending Supabase table migration"
     - No scripts to rewrite (the SKILL.md says it "joins live Baserow data" —
       may need to keep as reference until timesale tables exist in Supabase)

4.3  invoice-receipt-automation
     - Update local doc paths if Baserow ERP docs have moved
     - No API changes needed
```

---

## Execution Order & Dependencies

```
Session 0: Pre-flight audit
    │
Session 1: Phase 0 (retire 2) + Phase 1 (complete 2)         ← parallelizable
    │
Session 2: Phase 2 (migrate 3 x 886994 readers)               ← 3 skills, sequential
    │         + Governance PR for Phase 2 skills
    │
Session 3: Phase 3a (RPagentOS: 4 new tables)                 ← BLOCKS Phase 3b
    │
Session 4: Phase 3b (rewrite 4 write-heavy skills)            ← 4 skills, can parallel
    │         + Governance PRs for Phase 3 skills
    │
Session 5: Phase 4 (cleanup 3)                                ← quick, post-migration
    │         + Final audit: zero Baserow API references remain
```

## Rollback Safety

Each phase is independently committable and reversible:

| Phase | Rollback |
|-------|----------|
| P0 | `git revert` — skills were already non-functional against Baserow |
| P1 | Scripts still have Supabase path; flip `USE_SUPABASE=false` back |
| P2 | Skills read from existing view; no schema changes — `git revert` |
| P3a | New tables are additive; no existing data affected — can drop tables |
| P3b | Skills write to new tables; old Baserow data still exists — `git revert` |
| P4 | Documentation-only — `git revert` |

## Success Criteria

- [ ] Zero `api.baserow.io` references remain in `skills/` (grep confirms)
- [ ] All 11 active skills functional against Supabase
- [ ] All consumers registered in `rp-governance-kit` YAML files
- [ ] All write workloads have declarations in `DATABASE_WORKLOADS.yaml`
- [ ] All skills tested with dry-run against Supabase (reads succeed, writes to shadow)
- [ ] `baserow-database-manager` and `baserow-schema-editor` deleted
- [ ] `BASEROW_TOKEN` references removed from all `.env.example` and SKILL.md files
