---
name: amazon-listing-optimizer
description: |
  Amazon product listing optimization — end-to-end from research and content creation to image generation and CTR monitoring.
  Combines proven high-conversion templates ("4+2" bullet points, "X+1" image layout, "1+8+1+8+1" A+ structure)
  with automated workflows: hot keyword analysis, AI detail image generation, and CTR performance monitoring.
  Use when building or improving Amazon listings, writing bullet points, planning product images, designing A+ / EBC content,
  optimizing product titles with keywords, generating detail images, or monitoring listing performance.
trigger phrases:
  - "optimize product"
  - "generate product images"
  - "get hot keywords"
  - "optimize listing"
  - "create Amazon listing"
  - "improve listing"
  - "write bullet points"
  - "A+ content"
  - "EBC"
  - "CTR monitoring"
  - "detail images"
enabled: true
---

# Amazon Listing Optimizer

End-to-end Amazon listing optimization combining proven content templates with automated execution workflows. Covers the full lifecycle: research → content creation → image planning/generation → performance monitoring.

> **Scope:** For Amazon FBA product viability research, use `market-viability-logic-auditor`. For Etsy listing SEO, use `etsy-seo-optimizer`. For product trend timing, use `trend-stage-timing-analyzer`. For bulk inventory CSV generation, use `amazon-inventory-flatfile`. For SP-API image fetching, use `npm run job:amazon:fetch-images`.

---

## Overview

The skill operates in two layers:

| Layer | Focus | Source |
|-------|-------|--------|
| **Strategy** | Content rules, templates, proven patterns | amazon-listing-expert |
| **Execution** | Automation, keyword scraping, image generation, CTR monitoring | amz-product-optimizer |

---

## Layer 1: Strategy — Content Templates

### TD Template (Title & Description — Bullet Points)

- **Quantity**: Maximum 7 bullet points.
- **Format**: Selling Point — Description.
- **Content**: Follow the "4+2" formula:
  - **4 selling-point bullets**: Each bullet combines a selling point with a description that naturally incorporates consumer search keywords.
  - **2 supplementary bullets**: 1 bullet listing "What's in the Box" contents, and 1 bullet with warranty/care reminders or notes.
  - **1 optional bullet** (7th): Additional selling point or compatibility info if needed.

**Key Principles:**
- Focus on benefits, not just features
- Weave consumer search keywords naturally into descriptions — avoid keyword stuffing
- Keep each bullet concise but informative

**Title Formula**: `[Brand Name] + [Core Keyword] + [Product Feature] + [Material/Attribute] + [Size/Color]`

### Image Template: X + 1

The image template uses "X vertical images + 1 video" for mobile-first browsing.

| Slot | Type | Content |
|------|------|---------|
| 1 | **Main product image** (light gray/white background) | Product centered, clean composition, 20-30% padding |
| 2-5 | **Selling point lifestyle images** (3-4 images) | Product in real-use scenarios with selling point text overlay |
| 6 | **Accessories / bundle image** | Flat-lay of all included items |
| 7 | **Size / dimension reference** | Product next to familiar objects for scale |

**Video**: Demonstrate complete use/assembly process with selling point text overlays.

### A+ Product Description (EBC) — "1+8+1+8+1" Structure

| Section | Content | Purpose |
|---------|---------|---------|
| **1st "1"** | Product hero slogan | Full-width image or video with main value proposition |
| **1st "8"** | Feature selling points (8 modules) | Data-driven feature descriptions |
| **2nd "1"** | Lifestyle hero slogan | Full-width lifestyle image or video |
| **2nd "8"** | Scenario selling points (8 modules) | Use-case descriptions from review analysis |
| **3rd "1"** | Brand story | Social proof, certifications, team intro |

---

## Layer 2: Execution — Automation Workflows

### Core Capabilities

1. **AMZ123 Hot Keyword Scraping** — Real-time retrieval of Amazon US Top 250K search term ranking data
2. **Smart Product Title Optimization** — Optimize titles based on hot keywords, following the standard structure
3. **AI Detail Image Generation** — Auto-generate 5 scene-based product detail images (via Taobao MCP service)
4. **Main Image CTR Monitoring** — Scheduled monitoring, auto-identifying products needing optimization
5. **Local Data Auto-save** — Optimization results synced in real-time to local JSON/CSV files

### Execution Modes

| Mode | Description |
|------|-------------|
| `full` | Full flow: hot keywords + optimization + image generation |
| `keywords_only` | Hot keywords retrieval only |
| `optimize_names` | Product title optimization only |
| `generate_images` | Detail image generation only |
| `monitor` | CTR monitoring only |

### Full Flow

```
Step 1: Get Hot Keywords
  ↓ Scrape TOP 50 hot keywords from AMZ123

Step 2: Read Product Data
  ↓ Query products from local product_file (JSON/CSV)

Step 3: Optimize Product Titles
  ↓ Generate titles following: [Brand] + [Core Keyword] + [Feature] + [Spec]
  ↓ Prohibited: "Hot Search" and similar marker words, keyword stuffing

Step 4: Generate 5 Detail Images (via Taobao MCP)
  ↓ Main image: Cozy living room scene
  ↓ Detail 1: Bedroom bedside scene
  ↓ Detail 2: Product detail close-up
  ↓ Detail 3: Pet usage scene (marketing conversion)
  ↓ Detail 4: Sunny reading corner scene
  ↓ Detail 5: Reuse main image (visual consistency)

Step 5: Write to Local File
  ↓ Optimized title, main image, detail images 1-5

Step 6: Set Up CTR Monitoring
  ↓ Daily 10:00 check, threshold: < 5% flagged for optimization
```

---

## Full Workflow (Strategy + Execution)

### Creating a New Listing

1. **Research Phase**
   - Analyze 3-5 competitor listings
   - Fetch hot keywords from AMZ123
   - Identify keyword gaps and differentiation opportunities
   - Review customer feedback for pain points and selling angles

2. **TD Creation Phase**
   - Identify top 4 selling points from research
   - Write 7 bullet points following the "4+2" formula
   - Ensure consumer search keywords are woven naturally

3. **Image Planning Phase**
   - Plan the "X+1" image set based on selling points from TD
   - Generate 5 AI detail images with distinct scene-based prompts
   - Write detailed image briefs for each slot

4. **A+ Content Phase**
   - Build the "1+8+1+8+1" page structure
   - Feature modules based on product data; scenario modules based on review analysis
   - Include brand story with trust-building elements

5. **Review & Optimize**
   - Cross-check all components for consistency
   - Verify keyword coverage across bullet points and A+ content
   - Ensure A+ content complements rather than repeats bullet points

6. **Publish & Monitor**
   - Set up CTR monitoring (daily, 5% threshold)
   - A/B test main images with different scenes
   - Iterate based on performance analytics

---

## Input Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| keyword | string | Yes | Keyword to optimize | `"cat food"` |
| product_file | string | Yes | Product data file path | `"products.json"` |
| mode | string | No | Execution mode (`full`) | `full` |

---

## Common Mistakes to Avoid

| Mistake | Why It Matters |
|---------|---------------|
| Writing more than 7 bullet points | The "4+2" structure ensures complete coverage without overwhelming |
| Feature-only descriptions | Lead with what the customer gains, not just specs |
| Low-resolution or inconsistent images | Below 2000x2000 can't zoom; inconsistent styles look unprofessional |
| Duplicating bullet points in A+ | A+ should expand and complement, not repeat verbatim |
| "Hot Search" or similar marker words in titles | Platform violation |
| Keyword stuffing | Reduces readability and conversion; keywords should flow naturally |
| Mismatched images and selling points | Each lifestyle image must correspond to a specific selling point |
| Ignoring competitor analysis | Missed differentiation opportunities |

---

## Quick Reference

**Bullet points**: 7 max, "4+2" formula (4 selling points + what's-in-box + warranty)

**Title**: `[Brand] + [Core Keyword] + [Product Feature] + [Material/Attribute] + [Size/Color]`

**Images**: X vertical images + 1 video; main image on white/gray, lifestyle images with selling point text

**Detail images**: 5 scene-based (living room, bedroom, close-up, pet usage, reading corner)

**A+ content**: "1+8+1+8+1" = hero → features → hero → scenarios → brand story

**CTR monitoring**: Daily 10:00, < 5% threshold, A/B test main images

---

## Dependencies

### MCP Services

| Service Name | Server ID | Purpose |
|-------------|----------|---------|
| **Taobao opc Service** | `19cf03a191f` | Taobao image generation (create_picture_from_tb) |

### Python Dependencies

```bash
pip install requests>=2.28.0
pip install beautifulsoup4>=4.11.0
```

---

## Output

```json
{
  "status": "success",
  "mode": "full",
  "keywordsCount": 50,
  "optimizedProductsCount": 2,
  "generatedImagesCount": 10,
  "duration": "45.2s"
}
```

---

## Troubleshooting

| Error Code | Description | Solution |
|-----------|-------------|----------|
| KEYWORD_NOT_FOUND | No hot keyword data | Try a more popular keyword |
| IMAGE_GENERATION_FAILED | Image generation failed | Check original image link validity |
| TABLE_WRITE_ERROR | Table write failed | Verify field types and permissions |
| INVALID_TITLE_FORMAT | Title format error | Regenerate following standard structure |

---

## Version History

### v1.0.0 (2026-07-06)
- ✅ Merged `amazon-listing-expert` (content templates: "4+2", "X+1", "1+8+1+8+1")
- ✅ Merged `amz-product-optimizer` (automation: keywords, image generation, CTR monitoring)
- ✅ Deduplicated overlap and unified into two-layer architecture (Strategy + Execution)

## Technical Support

- **Author**: Retailpulses GK
- **Sources**: amazon-listing-expert (content strategy), amz-product-optimizer (automation workflows, Beiyechuan/Bug Zhuanjia)
