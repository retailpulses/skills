# Sync Job Inventory

Baseline status: reconstructed
Last runtime verification: 2026-07-19
Inventory owner: retailpulses/skills

## Authority

This file is the authoritative repository record of intended and known production sync workloads for the skills repository. Runtime infrastructure (VPS crontab, systemd timers, Cloudflare Cron Triggers, GitHub Actions schedules) is the source of truth for what is currently executing. Differences between this inventory and runtime are **governance drift** — a signal to investigate, not automatic permission to modify either side.

Governance invariants are defined in the canonical `SYNC_WORKLOAD_GOVERNANCE.md` policy in `retailpulses/rp-governance-kit`.

## Workloads

| Workload ID | Purpose | Kind / Effect | Runtime | Trigger | Source → Target | Entrypoint | Lifecycle | Deployment | Operational |
|---|---|---|---|---|---|---|---|---|---|
| `skills_sync_giga_products` | Sync GigaB2B products to Supabase | pull / internal_write | MacBook/manual | manual | GigaB2B API → Supabase product_variants + product_commercials | `sync-giga-saved-products/scripts/sync_to_supabase.py` | active | deployed | healthy |
| `skills_mercari_csv_listing_read` | Build Mercari listing CSVs from Supabase | projection / read_only | MacBook/manual | manual | Supabase baserow_886994_compat_vw → CSV | `mercari-csv-listing/scripts/build_mercari_listing_csv.py` | active | deployed | healthy |
| `skills_mercari_category_id` | Populate Mercari category IDs | projection / internal_write | MacBook/manual | manual | Supabase baserow_886994_compat_vw → Supabase product_variants | `mercari-category-id/SKILL.md` (agent-driven) | active | deployed | healthy |
| `skills_mercari_listing_id_sync` | Sync Mercari listing IDs to Supabase | reconcile / internal_write | ConoHa VPS | manual | Mercari API → Supabase platform_listings | `mercariops/tools/mercari-listing-id-sync/sync_mercari_listing_ids.py` | active | deployed | healthy |
| `skills_mercari_add_variant` | Create multi-variant Mercari listings | push / external_write | ConoHa VPS | manual | Supabase baserow_886994_compat_vw → Mercari API | `mercariops/tools/add-variant/add_mercari_variant.py` | active | deployed | healthy |
| `skills_amazon_inventory_flatfile` | Sync Amazon inventory and build flat files | pull / internal_write | MacBook/manual | manual | Supabase baserow_886994_compat_vw → Supabase amazon_listings | `amazon-inventory-flatfile/scripts/build_inventory_flatfile.py` | migrating | deployed | degraded |
| `skills_giga_resource_pack_copywriting` | Generate marketplace copy from Giga packs | pull / internal_write | MacBook/manual | manual | GigaB2B API → Supabase copywriting_outputs | `giga-resource-pack-copywriting/scripts/generate_copywriting_rows.py` | migrating | deployed | degraded |
| `skills_mercari_batch_update` | Batch update Mercari listings | push / external_write | MacBook/manual | manual | CSV → Mercari API + Supabase mercari_batch_update_log | `mercari-batch-update/scripts/mercari_batch_update.py` | migrating | deployed | degraded |
| `skills_mercari_inquiry_follow_up` | Follow up Mercari inquiries | pull / internal_write | MacBook/manual | manual | Supabase mercari_inquiries → Mercari Shops web | `mercari-inquiry-follow-up/scripts/supabase_inquiries.mjs` | migrating | deployed | degraded |

## Workload Details

### skills_sync_giga_products

- **Purpose:** Sync normalized GigaB2B product data into Supabase product_variants + product_commercials
- **Kind / Effect / Risk:** pull / internal_write / medium
- **Runtime host:** MacBook (manual) or VPS (scheduled, future)
- **Trigger / Schedule:** manual (`--apply` flag required)
- **Canonical source:** `sync-giga-saved-products/scripts/sync_to_supabase.py`
- **Deployment entrypoint:** `python3 sync-giga-saved-products/scripts/sync_to_supabase.py --apply`
- **Source system(s):** GigaB2B API (detailInfo, price, inventory)
- **Target system(s):** Supabase product_variants, product_commercials
- **Kill switch:** `Ctrl-C` (manual run); env var `SYNC_GIGA_PRODUCTS_ENABLED=false` for scheduled
- **Idempotency / deduplication:** Skip by `item_code` (unique key). Default create-only mode.
- **Checkpoint / replay:** Item Code list is checkpoint; re-run with same codes is safe (skips existing)
- **Overlapping writers:** None (sole writer of Giga→Supabase product sync)
- **Upstream dependencies:** GigaB2B API availability
- **Downstream consumers:** mercari-csv-listing, mercari-category-id, amazon-inventory-flatfile
- **Known limitations:** Ghost SKU handling; variant pricing propagation from canonical implementation only
- **Runtime verification:** `python3 sync_to_supabase.py` (dry-run mode)

### skills_mercari_csv_listing_read

- **Purpose:** Build Mercari listing CSVs from Supabase product data
- **Kind / Effect / Risk:** projection / read_only / low
- **Runtime host:** MacBook (manual)
- **Trigger / Schedule:** manual
- **Canonical source:** `mercari-csv-listing/scripts/build_mercari_listing_csv.py`
- **Deployment entrypoint:** `python3 mercari-csv-listing/scripts/build_mercari_listing_csv.py --item-codes <file>`
- **Source system(s):** Supabase baserow_886994_compat_vw
- **Target system(s):** CSV file (manual Mercari admin panel upload)
- **Kill switch:** N/A (read-only, no writes to any system)
- **Idempotency / deduplication:** N/A (read-only)
- **Checkpoint / replay:** Input item code list is the checkpoint
- **Overlapping writers:** None (read-only)
- **Upstream dependencies:** skills_sync_giga_products (for product data freshness)
- **Downstream consumers:** Mercari admin panel (manual CSV upload)
- **Known limitations:** Mercari max 20 images; shipping-fee guide image occupies last slot
- **Runtime verification:** `python3 build_mercari_listing_csv.py --dry-run`

### skills_mercari_category_id

- **Purpose:** Populate Mercari category IDs in Supabase from category master data
- **Kind / Effect / Risk:** projection / internal_write / low
- **Runtime host:** MacBook (manual)
- **Trigger / Schedule:** manual, agent-driven
- **Canonical source:** `mercari-category-id/SKILL.md` (agent instruction)
- **Deployment entrypoint:** Agent-driven PostgREST PATCH to product_variants
- **Source system(s):** Supabase baserow_886994_compat_vw, category master CSV
- **Target system(s):** Supabase product_variants.mercari_category_id
- **Kill switch:** Agent task cancellation
- **Idempotency / deduplication:** 100-row pilot → batch write → read-back verify
- **Checkpoint / replay:** Rows with empty mercari_category_id are candidates; re-running skips filled rows
- **Overlapping writers:** None (sole writer of mercari_category_id via this skill)
- **Upstream dependencies:** Category master CSV; skills_sync_giga_products (for product data)
- **Downstream consumers:** skills_mercari_csv_listing_read
- **Known limitations:** Parent-category fallback for ambiguous titles; conservative matching
- **Runtime verification:** PostgREST query for NULL mercari_category_id count

### skills_mercari_listing_id_sync

- **Purpose:** Backfill Mercari product IDs to Supabase platform_listings
- **Kind / Effect / Risk:** reconcile / internal_write / medium
- **Runtime host:** ConoHa VPS (Mercari API calls require Japan IP via SSH tunnel)
- **Trigger / Schedule:** manual
- **Canonical source:** `mercariops/tools/mercari-listing-id-sync/sync_mercari_listing_ids.py`
- **Deployment entrypoint:** `python3 sync_mercari_listing_ids.py --shop <N> --confirm`
- **Source system(s):** Mercari GraphQL API, Supabase baserow_886994_compat_vw
- **Target system(s):** Supabase platform_listings (mercari_shop{N}_product_id)
- **Kill switch:** `Ctrl-C`; `--dry-run` is default (no writes without `--confirm`)
- **Idempotency / deduplication:** Skip rows where target field already populated
- **Checkpoint / replay:** Re-running discovers only unfilled rows
- **Overlapping writers:** CatalogSync Mercari shop projections (read-only, disjoint — CatalogSync reads, this writes listing IDs)
- **Upstream dependencies:** Mercari API; ConoHa VPS SSH tunnel
- **Downstream consumers:** mercari-batch-update, mercari-add-variant
- **Known limitations:** Rate limited (0.3s between calls); max 10 products per page
- **Runtime verification:** `python3 sync_mercari_listing_ids.py --shop <N> --dry-run --max-skus 5`

### skills_mercari_add_variant

- **Purpose:** Create multi-variant Mercari listings from Supabase SPU1 groups
- **Kind / Effect / Risk:** push / external_write / high
- **Runtime host:** ConoHa VPS (Mercari API calls require Japan IP via SSH tunnel)
- **Trigger / Schedule:** manual
- **Canonical source:** `mercariops/tools/add-variant/add_mercari_variant.py`
- **Deployment entrypoint:** `python3 add_mercari_variant.py --sku <SKU> --shop <N> --execute`
- **Source system(s):** Supabase baserow_886994_compat_vw
- **Target system(s):** Mercari Shops API (createProduct mutation)
- **Kill switch:** `--dry-run` default; `--execute` required for live mutations
- **Idempotency / deduplication:** Creates new product (not idempotent). Pre-check: skip if SKU already has listing on target shop.
- **Checkpoint / replay:** Not replayable without manual cleanup (creates duplicate listings if re-run)
- **Overlapping writers:** skills_mercari_csv_listing_read (both create listings; coordinated by operator)
- **Upstream dependencies:** Mercari API; ConoHa VPS SSH tunnel; skills_mercari_listing_id_sync
- **Downstream consumers:** None (terminal — listing creation)
- **Known limitations:** Cannot add variants to existing products (API constraint); max 10 variants
- **Runtime verification:** `python3 add_mercari_variant.py --sku <SKU> --shop <N> --dry-run`

### skills_amazon_inventory_flatfile

- **Purpose:** Sync Amazon listing inventory and generate upload flat files
- **Kind / Effect / Risk:** pull / internal_write / medium
- **Runtime host:** MacBook (manual)
- **Trigger / Schedule:** manual
- **Canonical source:** `amazon-inventory-flatfile/scripts/build_inventory_flatfile.py`
- **Deployment entrypoint:** `python3 build_inventory_flatfile.py --template <xlsm> --output <dir>`
- **Source system(s):** Supabase baserow_886994_compat_vw
- **Target system(s):** Supabase amazon_listings, Amazon flat file (.txt)
- **Kill switch:** `Ctrl-C` (manual run)
- **Idempotency / deduplication:** Match by item_code; write quantity only
- **Checkpoint / replay:** Re-running overwrites amazon_listings.quantity safely
- **Overlapping writers:** None (sole writer of amazon_listings)
- **Upstream dependencies:** Amazon PriceAndQuantity.xlsm template; skills_sync_giga_products
- **Downstream consumers:** Amazon Seller Central (manual upload)
- **Known limitations:** Script code still uses Baserow API (migration TODO); Supabase amazon_listings table pending RPagentOS migration push
- **Runtime verification:** `python3 build_inventory_flatfile.py --dry-run`
- **Migration status:** ⚠️ Script needs Supabase rewrite. See `docs/BASEROW_TO_SUPABASE_MIGRATION.md`.

### skills_giga_resource_pack_copywriting

- **Purpose:** Generate Japanese marketplace copy from Giga resource packs
- **Kind / Effect / Risk:** pull / internal_write / low
- **Runtime host:** MacBook (manual)
- **Trigger / Schedule:** manual
- **Canonical source:** `giga-resource-pack-copywriting/scripts/generate_copywriting_rows.py`
- **Deployment entrypoint:** `python3 generate_copywriting_rows.py --item-code <CODE>`
- **Source system(s):** GigaB2B API, Supabase resource_packs
- **Target system(s):** Supabase copywriting_outputs
- **Kill switch:** `Ctrl-C` (manual run)
- **Idempotency / deduplication:** Write per item_code + platform; re-running overwrites
- **Checkpoint / replay:** Item Code is checkpoint; safe to re-run
- **Overlapping writers:** None
- **Upstream dependencies:** GigaB2B API; Supabase resource_packs table (pending RPagentOS migration)
- **Downstream consumers:** Manual copy review; CSV export for marketplace upload
- **Known limitations:** Script code still uses Baserow API (migration TODO); Supabase resource_packs/platform_copy_strategies/copywriting_outputs tables pending RPagentOS migration push
- **Runtime verification:** `python3 generate_copywriting_rows.py --dry-run`
- **Migration status:** ⚠️ Script needs Supabase rewrite. See `docs/BASEROW_TO_SUPABASE_MIGRATION.md`.

### skills_mercari_batch_update

- **Purpose:** Batch update Mercari listing fields and log results
- **Kind / Effect / Risk:** push / external_write / high
- **Runtime host:** MacBook (manual)
- **Trigger / Schedule:** manual
- **Canonical source:** `mercari-batch-update/scripts/mercari_batch_update.py`
- **Deployment entrypoint:** `python3 mercari_batch_update.py --csv <file> --confirm`
- **Source system(s):** CSV input, Mercari API
- **Target system(s):** Mercari Shops API (updateProduct), Supabase mercari_batch_update_log
- **Kill switch:** `--dry-run` default; `--confirm` required; `Ctrl-C`
- **Idempotency / deduplication:** Per-row mutation; re-running same CSV applies same changes
- **Checkpoint / replay:** Batch results logged to mercari_batch_update_log; partial runs are traceable
- **Overlapping writers:** CatalogSync Mercari projections (CatalogSync reconciles inventory; this updates price/title/description/category — disjoint field sets)
- **Upstream dependencies:** Mercari API; Supabase mercari_batch_update_log table (pending RPagentOS migration)
- **Downstream consumers:** None (terminal — listing mutation)
- **Known limitations:** Script uses baserow_client for logging (migration TODO); Supabase mercari_batch_update_log table pending RPagentOS migration push
- **Runtime verification:** `python3 mercari_batch_update.py --csv <file> --dry-run`
- **Migration status:** ⚠️ baserow_client dependency needs Supabase rewrite. See `docs/BASEROW_TO_SUPABASE_MIGRATION.md`.

### skills_mercari_inquiry_follow_up

- **Purpose:** Query and update Mercari inquiry records, send follow-ups
- **Kind / Effect / Risk:** pull / internal_write / medium
- **Runtime host:** MacBook (manual)
- **Trigger / Schedule:** manual (N-5 through N-2 day window)
- **Canonical source:** `mercari-inquiry-follow-up/scripts/supabase_inquiries.mjs`
- **Deployment entrypoint:** `node supabase_inquiries.mjs`
- **Source system(s):** Supabase mercari_inquiries, Mercari Shops web
- **Target system(s):** Supabase mercari_inquiries (status updates), Mercari Shops (messages)
- **Kill switch:** `Ctrl-C` (manual run); browser window close
- **Idempotency / deduplication:** Check follow_up_sent_at before sending; skip already-processed inquiries
- **Checkpoint / replay:** Inquiry status field is checkpoint; re-running skips sent inquiries
- **Overlapping writers:** None (sole writer of mercari_inquiries)
- **Upstream dependencies:** Supabase mercari_inquiries table (pending RPagentOS migration); Mercari Shops seller profile
- **Downstream consumers:** None
- **Known limitations:** Script code still uses Baserow API (migration TODO); Supabase mercari_inquiries table pending RPagentOS migration push; browser-based sending requires logged-in profile
- **Runtime verification:** `node supabase_inquiries.mjs --dry-run`
- **Migration status:** ⚠️ Script needs Supabase rewrite. See `docs/BASEROW_TO_SUPABASE_MIGRATION.md`.

---

## State Definitions

### Lifecycle State

| State | Meaning |
|-------|---------|
| `active` | Intended to run in production |
| `migrating` | Moving from Baserow to Supabase backend |
| `retiring` | Scheduled for removal; still running during transition |
| `retired` | No longer running; retained for historical reference |

### Deployment State

| State | Meaning |
|-------|---------|
| `deployed` | Code is present and runnable |
| `absent` | No code deployed |

### Operational State

| State | Meaning |
|-------|---------|
| `healthy` | Running successfully within expected parameters |
| `degraded` | Running with known issues (e.g., uses legacy Baserow API pending Supabase migration) |
| `broken` | Failing; output unreliable or absent |
| `unknown` | Runtime state has not been verified recently |

---

## Drift Log

| Date | Workload ID | Drift description | Resolution |
|------|-------------|-------------------|------------|
| 2026-07-19 | skills_amazon_inventory_flatfile | Script uses api.baserow.io; Supabase equivalent exists but code not yet migrated | Migrated SKILL.md + references; script flagged with TODO; migration pending RPagentOS table creation |
| 2026-07-19 | skills_giga_resource_pack_copywriting | Script uses api.baserow.io; Supabase tables pending RPagentOS migration | Migrated SKILL.md + references; script flagged with TODO |
| 2026-07-19 | skills_mercari_batch_update | Script uses baserow_client; Supabase table pending RPagentOS migration | Migrated SKILL.md + references; script flagged with TODO |
| 2026-07-19 | skills_mercari_inquiry_follow_up | Script uses api.baserow.io; Supabase table pending RPagentOS migration | Migrated SKILL.md + references; script flagged with TODO; baserow_inquiries.mjs renamed to supabase_inquiries.mjs |

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| v0.1.0 | 2026-07-19 | Initial baseline — reconstructed from Baserow→Supabase migration |
