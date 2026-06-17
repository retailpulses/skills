# Mercari CSV Listing Skill

Generates Mercari listing CSVs from Item Codes using Baserow Products table (886994) and GigaB2B API for seller-paid shipping listings.

## Prerequisites

- Python 3.9+
- `pip install -r requirements.txt`
- `BASEROW_TOKEN` in environment or `.env`
- `GIGA_CLIENT_ID` and `GIGA_CLIENT_SECRET` for GigaB2B image fetching
- Mercari template CSV (`mercari_template.csv` — 168 columns, UTF-8 BOM)

## Usage

```bash
python3 scripts/build_mercari_listing_csv.py \
  --item-codes "<comma-separated-codes-or-file>" \
  --template-csv "<mercari_template.csv>" \
  --shipping-guide-url "<shipping-fee-guide-image-url>" \
  --score \
  --auto-open-qualified
```

### Key flags

| Flag | Description |
|------|-------------|
| `--score` | Enable 10-module quality scoring (100-point rubric) |
| `--auto-open-qualified` | Set `商品ステータス=2` for listings scoring >= 80 |
| `--baserow-workers` | Parallel Baserow read workers (default: 10) |
| `--output-path` | Custom output CSV path |

## Data Sources

| Field | Source |
|-------|--------|
| `商品名` | 886994.`Product Name` |
| `商品説明` | 886994.`Product Specification` |
| `SKU1_種類` | 886994.`Representative_Color_JA` |
| `SKU1_在庫数` | 886994.`Mercari Qty` |
| `販売価格` | 886994.`Mercari Effective Pricing (incl. shipping)` |
| `カテゴリID` | 886994.`Mercari category ID` |
| Images | 886994.`Image URLs JSON` > GigaB2B API (`imageUrls`) |

## Image Resolution

1. `Image URLs JSON` from Baserow (JSON array of URLs)
2. Fallback to GigaB2B product detail API (`imageUrls` field)
3. Append shipping-fee guide image as last slot
4. Cap at 20 images

## Scoring (10 modules, 100 points)

Threshold: >= 80 and no blocking gates → auto-open (`商品ステータス=2`)

| Module | Max Points |
|--------|-----------|
| Title | 14 |
| Description | 14 |
| Images | 14 |
| Category | 12 |
| Pricing | 12 |
| Variant (`SKU1_種類`) | 8 |
| Inventory | 8 |
| Shipping Guide | 6 |
| Discount | 6 |
| Spec Length | 6 |

### Blocking Gates
- `BLOCKED:no_title` — title empty or >130 chars
- `BLOCKED:no_description` — description empty or >3000 chars
- `BLOCKED:no_images` — 0 valid images
- `BLOCKED:no_price` — price = 0 or empty

## Output

- `mercari_listing_YYYY-MM-DD.csv` — listing CSV (UTF-8 BOM, CRLF)
- `quality_scores_YYYY-MM-DD.csv` — scoring sidecar (with `--score`)
- `missing_products_YYYY-MM-DD.csv` — codes not found in 886994

## File Structure

```
skills/mercari-csv-listing/
├── README.md           # This file
├── SKILL.md            # Agent skill definition
├── requirements.txt    # Python dependencies
├── scripts/
│   ├── build_mercari_listing_csv.py              # Main CSV builder
│   ├── mercari_text_utils.py                     # GigaB2B API + text utils
│   ├── prepare_oversize_images_for_mercari.py
│   ├── upload_mercari_csv_to_shops.py            # Multi-shop CSV upload
│   └── create_resize_product_images_bucket.sh
└── references/
    ├── api-upload-multishop.md
    └── image-preprocessing-r2.md
```
