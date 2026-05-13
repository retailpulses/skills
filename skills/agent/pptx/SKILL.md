---
name: pptx
description: "Presentation creation, editing, and analysis. When Claude needs to work with presentations (.pptx files) for: (1) Creating new presentations, (2) Modifying or editing content, (3) Working with layouts, (4) Adding comments or speaker notes, or any other presentation tasks"
---

# PPTX creation, editing, and analysis

## Overview

A user may ask you to create, edit, or analyze the contents of a .pptx file. A .pptx file is essentially a ZIP archive containing XML files and other resources that you can read or edit. You have different tools and workflows available for different tasks.

## Setup — run this FIRST (mandatory, idempotent)

This skill ships with a pinned `package.json` for required Node deps (`pptxgenjs`, `playwright`, `sharp`, `react`, `react-dom`, `react-icons`).
**Before any html2pptx / thumbnail_html workflow**, run the bootstrap script.

```bash
bash "{skillDir}/bootstrap.sh"
```

- Idempotent: first run installs (~30s + ~150MB Playwright Chromium); reruns finish in <100ms.
- Your own scripts run from a separate workspace dir — prefix `node` invocations with `export NODE_PATH="{skillDir}/node_modules"` so `require('pptxgenjs')` etc. resolve.

## Reading and analyzing content

### Text extraction
For plain text content, convert to markdown:

```bash
python -m markitdown path-to-file.pptx
```

### Raw XML access
Needed for: comments, speaker notes, slide layouts, animations, design elements, complex formatting.

Unpack: `python ooxml/scripts/unpack.py <office_file> <output_dir>` (if missing, run `find . -name "unpack.py"`).

Key files inside the unpacked archive:
* `ppt/presentation.xml` — main metadata and slide references
* `ppt/slides/slide{N}.xml` — slide contents
* `ppt/notesSlides/notesSlide{N}.xml` — speaker notes
* `ppt/comments/modernComment_*.xml` — comments
* `ppt/slideLayouts/`, `ppt/slideMasters/`, `ppt/theme/`, `ppt/media/` — layouts, masters, theme, media

**Typography/color extraction (when emulating an example design)**:
1. Theme: `ppt/theme/theme1.xml` → `<a:clrScheme>` and `<a:fontScheme>`
2. Sample slide: `ppt/slides/slide1.xml` → `<a:rPr>` for actual font usage
3. Grep `<a:solidFill>`, `<a:srgbClr>`, font refs across all XML files

## Creating a new PowerPoint presentation **without a template**

When creating a new PowerPoint presentation from scratch, follow the Workflow below to convert HTML slides to PowerPoint via **html2pptx** — and ⚠️ **you MUST first read [`html2pptx.md`](html2pptx.md) in full** (no range limits) for the methods, rules, examples, and gotchas it relies on.

### Design Principles

**Before writing code**, analyze the content and state your design approach:
1. Subject matter — tone, industry, mood
2. Branding — company colors/identity if mentioned
3. Match palette to content
4. State the approach in chat before coding

**Requirements**:
- Web-safe fonts only: Arial, Helvetica, Times New Roman, Georgia, Courier New, Verdana, Tahoma, Trebuchet MS, Impact
- Clear visual hierarchy (size, weight, color); strong contrast and clean alignment
- Consistent patterns/spacing/visual language across slides

#### Color Palette Selection

- Think beyond defaults; avoid autopilot (healthcare ≠ always green, finance ≠ always navy)
- Consider topic, industry, mood, energy, audience, brand
- Pick 3–5 working colors (dominant + supporting + accent)
- Ensure text/background contrast

**Example color palettes** (spark creativity — pick one, adapt it, or build your own):

1. **Classic Blue**: navy (#1C2833), slate (#2E4053), silver (#AAB7B8), off-white (#F4F6F6)
2. **Teal & Coral**: teal (#5EA8A7), deep teal (#277884), coral (#FE4447), white (#FFFFFF)
3. **Burgundy Luxury**: burgundy (#5D1D2E), crimson (#951233), rust (#C15937), gold (#997929)
4. **Sage & Terracotta**: sage (#87A96B), terracotta (#E07A5F), cream (#F4F1DE), charcoal (#2C2C2C)
5. **Black & Gold**: gold (#BF9A4A), black (#000000), cream (#F4F6F6)
6. **Vibrant Orange**: orange (#F96D00), light gray (#F2F2F2), charcoal (#222831)
7. **Forest Green**: black (#191A19), green (#4E9F3D), dark green (#1E5128), white (#FFFFFF)
8. **Retro Rainbow**: purple (#722880), pink (#D72D51), orange (#EB5C18), amber (#F08800), gold (#DEB600)
9. **Warm Blush**: mauve (#A49393), blush (#EED6D3), rose (#E8B4B8), cream (#FAF7F2)
10. **Deep Purple & Emerald**: purple (#B165FB), dark blue (#181B24), emerald (#40695B), white (#FFFFFF)

#### Visual Details Options

- **Geometric**: diagonal dividers, asymmetric columns (30/70, 40/60), rotated 90°/270° headers, circular/hexagonal image frames, triangular corner accents, overlapping shapes for depth.
- **Borders & Frames**: thick single-side borders (10–20pt), double-line contrasting borders, corner brackets, L-shaped borders, thick underline accents (3–5pt).
- **Typography**: extreme size contrast (72pt vs 11pt), all-caps + wide letter-spacing, oversized numbered sections, monospace (Courier New) for data, condensed (Arial Narrow) for dense text, outlined text for emphasis.
- **Charts & Data**: monochrome with single accent, horizontal bars, dot plots, minimal/no gridlines, inline data labels (no legends), oversized key metrics.
- **Layout**: full-bleed image + text overlay, 20–30% sidebar, modular 3×3/4×4 grids, Z/F-pattern flow, floating boxes over shapes, magazine multi-column.
- **Background**: solid color blocks (40–60% of slide), vertical/diagonal gradients, split (two-color) backgrounds, edge-to-edge bands, deliberate negative space.

### Layout Tips (slides with charts/tables)
- **Two-column (PREFERRED)**: full-width header + two columns (text/bullets vs featured content). Use flexbox with unequal widths (e.g., 40/60).
- **Full-slide**: let chart/table take the entire slide for maximum impact.
- **NEVER vertically stack** chart/table below text in a single column — poor readability.

### Workflow
1. **MANDATORY - READ ENTIRE FILE**: Read [`html2pptx.md`](html2pptx.md) completely from start to finish. **NEVER set any range limits when reading this file.** Read the full file content for detailed syntax, critical formatting rules, and best practices before proceeding with presentation creation.
2. Create an HTML file for each slide with proper dimensions (e.g., 720pt × 405pt for 16:9)
   - HTML carries **only static visual content** (text, headings, lists, decorative shapes, images). **Charts and tables are NOT written in HTML** — leave a `class="placeholder"` div for them and add the real chart/table in step 3 via PptxGenJS, otherwise they vanish from the PPTX.
   - Use `<p>`, `<h1>`-`<h6>`, `<ul>`, `<ol>` for all text content
   - **CRITICAL**: Rasterize gradients and icons as PNG images FIRST using Sharp, then reference in HTML
   - **LAYOUT**: For slides with charts/tables/images, use either full-slide layout or two-column layout for better readability
   - **AVOID common build errors** (each one forces a rebuild — see [`html2pptx.md`](html2pptx.md) for details):
     - ❌ `<table>`/`<tr>`/`<td>` (also `<svg>`, `<canvas>`, `<iframe>`) → silently dropped; use a `placeholder` + `slide.addTable(...)` in build.js
     - ❌ `background` / `border` / `box-shadow` on `<p>`, `<h*>`, `<ul>`, `<ol>` → wrap them in a `<div>` carrying the style
     - ❌ `margin` on inline tags (`<b>`, `<i>`, `<u>`, `<span>`) → not supported in PowerPoint, use spaces, padding on parent, or move to a block element
3. Write & run a `build.js` using the [`html2pptx.js`](scripts/html2pptx.js) library:
   - Copy `html2pptx.js` next to your script and import with `const html2pptx = require('./html2pptx');`
   - Call `html2pptx()` per HTML file; add tables/charts into placeholders via the PptxGenJS API; save with `pptx.writeFile()`.
   - Wrap each slide in `try...catch` and collect all errors before reporting — fix them in one batch rather than one rebuild per slide (see *Complete Example* in [`html2pptx.md`](html2pptx.md)).
4. **Visual validation**: Generate thumbnails and inspect. Try in order, falling back only when the previous fails:
   - **Preferred — render the .pptx** (most accurate):
     ```bash
     python scripts/thumbnail.py output.pptx workspace/thumbnails --cols 4
     ```
     On `LibreOffice (soffice) not installed`, fall through.
   - **Fallback — screenshot source HTML via Playwright** (same DOM as html2pptx, ~1:1 preview):
     ```bash
     python scripts/thumbnail_html.py 'workspace/slide-*.html' workspace/thumbnails --cols 4
     ```
     If Playwright is missing, run `bash "{skillDir}/bootstrap.sh"` and retry.
     ⚠️ Empty `class="placeholder"` regions are EXPECTED (charts/tables come from `build.js`) — do NOT inline data into HTML to "fix" them; verify via `build.js`.
   - **Last resort — text grid** (no pixels, but still surfaces overflow/overlap):
     ```bash
     python scripts/inventory_textgrid.py output.pptx -o workspace/thumbnails.md
     ```
   - Inspect for: text cutoff (headers, shapes, edges), overlap, boundary spacing, contrast. Adjust HTML and regenerate until correct.

## Editing an existing PowerPoint presentation

Editing requires working with the raw Office Open XML (OOXML) format: unpack → edit XML → repack.

### Workflow
1. **MANDATORY — read [`ooxml.md`](ooxml.md) in full** (no range limits) before editing.
2. Unpack: `python ooxml/scripts/unpack.py <office_file> <output_dir>`
3. Edit XML files (primarily `ppt/slides/slide{N}.xml`).
4. **Validate after each edit** and fix errors before proceeding: `python ooxml/scripts/validate.py <dir> --original <file>`
5. Pack: `python ooxml/scripts/pack.py <input_directory> <office_file>`

## Creating a new PowerPoint presentation **using a template**

When you need to create a presentation that follows an existing template's design, you'll need to duplicate and re-arrange template slides before then replacing placeholder context.

### Workflow
1. **Extract template text + create thumbnail grid**:
   * Text: `python -m markitdown template.pptx > template-content.md` — then read the full file (no range limits).
   * Thumbnails: `python scripts/thumbnail.py template.pptx`
   * If `soffice` is unavailable, try installing it (see [Converting Slides to Images](#converting-slides-to-images)) and re-run. Only if install fails, fall back to text-grid (degraded — no pixels):
     ```bash
     python scripts/inventory_textgrid.py template.pptx -o template-textgrid.md
     ```
   * Details: see [Creating Thumbnail Grids](#creating-thumbnail-grids).

2. **Analyze template, save `template-inventory.md`** (required for next step):
   ```markdown
   # Template Inventory Analysis
   **Total Slides: [count]**
   **IMPORTANT: Slides are 0-indexed (first slide = 0, last slide = count-1)**

   ## [Category Name]
   - Slide 0: [Layout code] - Description/purpose
   - Slide 1: [Layout code] - Description/purpose
   [... list EVERY slide individually with its index ...]
   ```
   From the thumbnail grid identify: layout patterns (title/content/divider), image-placeholder locations & counts, design consistency, visual hierarchy.

3. **Create outline (`outline.md`) with content + template mapping**:
   * Pick a title/intro layout (usually one of the first slides) for slide 1; safe text-based layouts elsewhere.
   * **Match layout to actual content count**: 2-col → exactly 2 items; 3-col → exactly 3; image+text → only if you have images; quote → only for real attributed quotes. Never select layouts with more placeholders than content. If you have 4+ items, split slides or use a list.
   * Count content pieces BEFORE selecting; verify every placeholder will be filled meaningfully.
   * Example mapping (0-based; verify indices are within range — 73-slide template = indices 0–72):
      ```python
      template_mapping = [
          0,   # Title/Cover
          34,  # B1: Title + body
          34,  # duplicate B1
          50,  # E1: Quote
          54,  # F2: Closing
      ]
      ```

4. **Duplicate, reorder, delete via `rearrange.py`**:
   ```bash
   python scripts/rearrange.py template.pptx working.pptx 0,34,34,50,52
   ```
   Indices are 0-based; repeats duplicate the slide; unused slides are dropped.

5. **Extract all text via `inventory.py`**:
   ```bash
   python scripts/inventory.py working.pptx text-inventory.json
   ```
   Read `text-inventory.json` in full (no range limits) to see all shapes and properties.

   Inventory JSON structure:
   ```json
   {
     "slide-0": {
       "shape-0": {
         "placeholder_type": "TITLE",  // or null for non-placeholders
         "left": 1.5,                  // position in inches
         "top": 2.0,
         "width": 7.5,
         "height": 1.2,
         "paragraphs": [
           {
             "text": "Paragraph text",
             // Optional properties (only included when non-default):
             "bullet": true,           // explicit bullet detected
             "level": 0,               // only included when bullet is true
             "alignment": "CENTER",    // CENTER, RIGHT (not LEFT)
             "space_before": 10.0,     // points
             "space_after": 6.0,
             "line_spacing": 22.4,
             "font_name": "Arial",     // from first run
             "font_size": 14.0,        // points
             "bold": true,
             "italic": false,
             "underline": false,
             "color": "FF0000"         // RGB
           }
         ]
       }
     }
   }
   ```

   Key features:
   - Slides named `slide-0`, `slide-1`, …; shapes ordered top-to-bottom, left-to-right as `shape-0`, `shape-1`, …
   - Placeholder types: `TITLE`, `CENTER_TITLE`, `SUBTITLE`, `BODY`, `OBJECT`, or `null`
   - `default_font_size` (pt) extracted from layout placeholders when available
   - `SLIDE_NUMBER` placeholders auto-excluded
   - When `bullet: true`, `level` is always included (even if 0)
   - `space_before` / `space_after` / `line_spacing` in points (only when set)
   - `color` = RGB (e.g., `"FF0000"`); `theme_color` = theme name (e.g., `"DARK_1"`)
   - Only non-default values are included

6. **Generate replacements → `replacement-text.json`**

   Rules (the replace.py script enforces these):
   - Only reference shapes/slides actually present in the inventory — `replace.py` validates and reports all errors at once.
   - **Auto-clear**: every text shape in the inventory is cleared unless you supply `"paragraphs"` for it.
   - Use field name `"paragraphs"` (not `replacement_paragraphs`).
   - Bullets auto-left-align; do NOT set `alignment` when `"bullet": true`, and do NOT include bullet symbols (•, -, *) in text — added automatically.
   - Carry over paragraph properties from the original inventory; size content to fit shape dimensions.
   - **Formatting essentials**:
     - Headers/titles: `"bold": true`
     - List items: `"bullet": true, "level": 0` (level required when bullet is true)
     - Preserve original alignment (e.g., `"alignment": "CENTER"`)
     - Include font props only when different from default
     - Colors: `"color": "FF0000"` (RGB) or `"theme_color": "DARK_1"` (theme)
     - For overlapping shapes, prefer ones with larger `default_font_size` or more appropriate `placeholder_type`.

   Example `paragraphs` field:
   ```json
   "paragraphs": [
     {
       "text": "New presentation title text",
       "alignment": "CENTER",
       "bold": true
     },
     {
       "text": "Section Header",
       "bold": true
     },
     {
       "text": "First bullet point without bullet symbol",
       "bullet": true,
       "level": 0
     },
     {
       "text": "Red colored text",
       "color": "FF0000"
     },
     {
       "text": "Theme colored text",
       "theme_color": "DARK_1"
     },
     {
       "text": "Regular paragraph text without special formatting"
     }
   ]
   ```

   Shapes omitted from the JSON are auto-cleared:
   ```json
   {
     "slide-0": {
       "shape-0": { "paragraphs": [...] }
       // shape-1, shape-2 from inventory will be cleared automatically
     }
   }
   ```

   Common patterns: title slides (bold, sometimes centered) · section headers (bold) · bullet lists (`bullet: true, level: 0` each) · body text (usually no extras) · quotes (may need special alignment/font).

7. **Apply replacements**:
   ```bash
   python scripts/replace.py working.pptx replacement-text.json output.pptx
   ```
   The script extracts the inventory, validates, clears all text shapes, applies new paragraphs (with formatting), and saves.

   Example errors:
   ```
   ERROR: Invalid shapes in replacement JSON:
     - Shape 'shape-99' not found on 'slide-0'. Available shapes: shape-0, shape-1, shape-4
     - Slide 'slide-999' not found in inventory
   ```
   ```
   ERROR: Replacement text made overflow worse in these shapes:
     - slide-0/shape-2: overflow worsened by 1.25" (was 0.00", now 1.25")
   ```

## Creating Thumbnail Grids

Three ways to get a thumbnail grid — pick by what you have on disk and which deps are installed:

| Tool | Input | Needs | Output | Use when |
|------|-------|-------|--------|----------|
| `scripts/thumbnail.py` | `.pptx` | LibreOffice (`soffice`) + Poppler (`pdftoppm`) | JPG grid (pixel-accurate) | You have a `.pptx` and `soffice` is installed. |
| `scripts/thumbnail_html.py` | HTML files (`slide-*.html`) | Playwright (used by `html2pptx.js`) | JPG grid (pixel-accurate) | html2pptx workflow — same DOM, so it's a 1:1 preview without soffice. |
| `scripts/inventory_textgrid.py` | `.pptx` | Pure Python (`python-pptx`) | Markdown text grid | No `soffice`, no HTML. Lists each shape's bbox/font/color/text + overflow/overlap warnings. |

### `thumbnail.py` (pixel JPG from .pptx)

```bash
python scripts/thumbnail.py template.pptx [output_prefix]
```

- Creates `thumbnails.jpg` (or `-1.jpg`, `-2.jpg` for large decks). Slides are 0-indexed.
- Default: 5 cols, 30 slides/grid. `--cols 3..6` → 12 / 20 / 30 / 42 slides per grid.
- `output_prefix` may include a path (e.g., `workspace/my-grid`).
- If `soffice` is missing, install LibreOffice + Poppler (see [Converting Slides to Images](#converting-slides-to-images)) and retry. Only after install fails, fall back to `thumbnail_html.py` (if HTML sources exist) or `inventory_textgrid.py` (text-only, degraded).

### `thumbnail_html.py` (pixel JPG from HTML, no soffice)

```bash
python scripts/thumbnail_html.py 'workspace/slide-*.html' workspace/thumbnails --cols 4
```

- Quote the glob to prevent shell expansion (or pass an explicit ordered list).
- Renders each HTML at 960×540 (16:9); override with `--viewport 1280x720`.
- Same grid composer/output naming/limits as `thumbnail.py`.
- Tries Python `playwright` first, falls back to the Node Playwright html2pptx already uses.

### `inventory_textgrid.py` (text grid, no soffice, no HTML)

```bash
python scripts/inventory_textgrid.py template.pptx -o template-textgrid.md
python scripts/inventory_textgrid.py template.pptx --issues-only   # only flag layout problems
```

- Pure-Python (`python-pptx` only).
- Output Markdown: per-slide shape bbox (inches), representative font/size/color, text preview, inline `!!` warnings for edge overflow / frame overflow / overlap.

**Use cases**: template analysis, content review, slide navigation, layout QA.

## Converting Slides to Images

Two-step manual conversion (requires `soffice` + `pdftoppm` — install commands in [Dependencies](#dependencies)):

```bash
soffice --headless --convert-to pdf template.pptx       # 1. PPTX → PDF
pdftoppm -jpeg -r 150 template.pdf slide                # 2. PDF → slide-1.jpg, slide-2.jpg, ...
```

`pdftoppm` options: `-r 150` (DPI) · `-jpeg` / `-png` · `-f N` first page · `-l N` last page. Example range: `pdftoppm -jpeg -r 150 -f 2 -l 5 template.pdf slide`.

### Fallback when LibreOffice / Poppler install fails

Only after install has been attempted. Fallback is degraded, not equivalent.

- **HTML sources exist** (html2pptx workflow) → use [`thumbnail_html.py`](#thumbnail_htmlpy-pixel-jpg-from-html-no-soffice) (Playwright renders the same DOM, ~1:1 preview). If Playwright is missing, run `bash "{skillDir}/bootstrap.sh"` and retry.
- **Otherwise** → report failure and ask user to install LibreOffice + Poppler. Do NOT fall back to plain text grids when a pixel image was requested.

## Code Style
Write concise code: short variable names, no redundant operations, no unnecessary print statements.

## Dependencies

**Node** (managed by `package.json`, installed by `bootstrap.sh` — see [Setup](#setup--run-this-first-mandatory-idempotent)):
- `pptxgenjs` — html2pptx presentation building
- `playwright` — HTML rendering for html2pptx & thumbnail_html.py
- `sharp` — SVG rasterization / image processing
- `react` / `react-dom` / `react-icons` — JSX → HTML + icons

**Python**:
- `pip install "markitdown[pptx]"` — text extraction
- `pip install defusedxml` — secure XML parsing
- `pip install python-pptx` — used by thumbnail / inventory scripts

**Optional system tools** (PPTX → PDF → JPEG):
| Platform | LibreOffice (`soffice`) | Poppler (`pdftoppm`) |
|---|---|---|
| macOS | `brew install --cask libreoffice` | `brew install poppler` |
| Linux (Debian/Ubuntu) | `sudo apt-get install libreoffice` | `sudo apt-get install poppler-utils` |
| Windows | `choco install libreoffice` | `choco install poppler` |

If unavailable, fall back to `scripts/thumbnail_html.py` (when HTML sources exist) — uses the Playwright already installed by `bootstrap.sh`.