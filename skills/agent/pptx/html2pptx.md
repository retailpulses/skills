# HTML to PowerPoint Guide

Convert HTML slides to PowerPoint with accurate positioning via the `html2pptx.js` library.

Three sections: **Creating HTML Slides** · **Using the html2pptx Library** · **Using PptxGenJS** (for charts/tables/dynamic content).

---

## Creating HTML Slides

Every HTML slide must include proper body dimensions:

### Layout Dimensions

- **16:9** (default): `width: 720pt; height: 405pt`
- **4:3**: `width: 720pt; height: 540pt`
- **16:10**: `width: 720pt; height: 450pt`

### Safe Layout (avoid overflow / bottom-edge errors)

`html2pptx` enforces a 0.5" bottom margin for text > 12pt and rejects any body overflow. Build these guards into the HTML up front to avoid edit-build retry loops:

- **Reserve a bottom safe zone** on the body wrapper:
  ```css
  .wrap {
    width: 720pt; height: 405pt;
    padding: 24pt 40pt 48pt 40pt;  /* bottom 48pt ≈ 0.67", clears the 0.5" rule */
    box-sizing: border-box;
    overflow: hidden;               /* fail-safe; build still validates true overflow */
  }
  ```
- **Prefer flex over hard-coded margins** for vertical distribution — `display: flex; flex-direction: column;` plus `justify-content: space-between` adapts to text-length variance and rarely overflows.
- **Use CSS variables for shared sizes** (`--title-fs`, `--gap`) so a single edit rebalances the whole deck instead of per-slide tweaks.
- **Fix systemically, not page-by-page** — when one slide overflows due to a recurring pattern (e.g. card padding too large), apply the same fix to all slides built from that pattern in one pass.

### Supported Elements

- `<p>`, `<h1>`–`<h6>` — text with styling
- `<ul>`, `<ol>` — lists (never use manual bullets •, -, *)
- `<b>` / `<strong>`, `<i>` / `<em>`, `<u>` — inline formatting
- `<span>` — inline formatting via CSS (bold, italic, underline, color)
- `<br>` — line breaks
- `<div>` with bg/border — becomes a shape
- `<img>` — images
- `class="placeholder"` — reserved space for tables/charts (returns `{ id, x, y, w, h }`)

### Unsupported Elements (silent data loss — no build error)

`<table>` / `<tr>` / `<td>`, `<svg>`, `<canvas>`, `<iframe>`, `<video>`, `<audio>` render in a browser but get dropped from the PPTX.

Two ways to render a table:
1. **Native PowerPoint table (recommended for data-heavy)** — `class="placeholder"` div + `slide.addTable(...)` in `build.js`
2. **Div-grid mock-up (visual-only)** — rebuild the grid with nested `<div>`s, each cell wraps text in `<p>`

### Critical Text Rules

**ALL text MUST be inside `<p>`, `<h1>`–`<h6>`, `<ul>`, or `<ol>`** — text in bare `<div>` or `<span>` is silently dropped:
- ✅ `<div><p>Text here</p></div>`
- ❌ `<div>Text here</div>` / `<span>Text</span>` — will NOT appear in PowerPoint

**NEVER use manual bullet symbols (•, -, *)** — use `<ul>`/`<ol>`.

**ONLY web-safe fonts**: `Arial`, `Helvetica`, `Times New Roman`, `Georgia`, `Courier New`, `Verdana`, `Tahoma`, `Trebuchet MS`, `Impact`, `Comic Sans MS`. Custom fonts (`Segoe UI`, `SF Pro`, `Roboto`, etc.) may cause rendering issues.

### Styling

- Use `display: flex` on body — prevents margin collapse from breaking overflow validation.
- `margin` for spacing (padding is part of size). Flexbox positions are computed from rendered layout.
- Hex colors with `#` prefix in CSS (PptxGenJS API uses no `#` — see [Critical Rules](#-critical-rules)).
- **Inline formatting** via `<b>`/`<i>`/`<u>` or `<span>` with CSS (`font-weight`, `font-style`, `text-decoration`, `color`). `<span>` does NOT support `margin`/`padding` (PowerPoint text runs ignore them).
  - Example: `<span style="font-weight: bold; color: #667eea;">Bold blue</span>`
- **Text alignment**: CSS `text-align` (`center`, `right`, …) hints PptxGenJS formatting when text length varies slightly.

### Shape Styling (DIV elements only)

**Backgrounds, borders, border-radius, and shadows only work on `<div>`** — NOT on text elements (`<p>`, `<h*>`, `<ul>`, `<ol>`).

**Two build-time errors to avoid** (most common cause of rebuild loops):

1. **`background` / `border` / `border-radius` / `box-shadow` on a text element** — wrap in a styled `<div>`:
   ```html
   <!-- ❌ BUILD ERROR: Text element <p> has border. -->
   <p style="background: #f0f0f0; border-left: 4pt solid #333;">Card text</p>

   <!-- ✅ Move styling to a div wrapper -->
   <div style="background: #f0f0f0; border-left: 4pt solid #333; padding: 8pt;">
     <p>Card text</p>
   </div>
   ```
2. **`margin` on inline tags (`<b>`, `<i>`, `<u>`, `<span>`)** — text runs ignore margin:
   ```html
   <!-- ❌ BUILD ERROR: Inline element <b> has margin-right. -->
   <p>Label: <b style="margin-right: 8pt;">42</b> units</p>

   <!-- ✅ Use a space, padding on the parent, or a block element -->
   <p>Label: <b>42</b>&nbsp;&nbsp;units</p>
   ```

These rules apply to **every slide** — when one page hits them, scan siblings for the same pattern before rebuilding.

**Supported `<div>` styling**:
- **Backgrounds**: `background` / `background-color` → shape fill. e.g. `<div style="background: #f0f0f0;">`
- **Borders**: uniform (`border: 2px solid #333`) → shape border; partial (`border-left/right/top/bottom`) → line shapes. e.g. `<div style="border-left: 8pt solid #E76F51;">`
- **Border radius**: `border-radius` (px/pt/%) → rounded corners. `≥50%` → circular. `<50%` is relative to the shape's smaller dimension (e.g. 25% on a 100×200 box = 25px). e.g. `border-radius: 8pt;`
- **Box shadows**: outer shadows only (insets are silently skipped to avoid corruption). e.g. `<div style="box-shadow: 2px 2px 8px rgba(0,0,0,0.3);">`

### Icons & Gradients

**CRITICAL: Never use CSS gradients (`linear-gradient`, `radial-gradient`)** — they don't convert to PowerPoint. Pre-rasterize all gradients (SVG → PNG) and icons (react-icons SVG → PNG) with Sharp **before** HTML rendering, then reference the PNG.

**Rasterizing Icons with Sharp:**

```javascript
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const sharp = require('sharp');
const { FaHome } = require('react-icons/fa');

async function rasterizeIconPng(IconComponent, color, size = "256", filename) {
  const svgString = ReactDOMServer.renderToStaticMarkup(
    React.createElement(IconComponent, { color: `#${color}`, size: size })
  );

  // Convert SVG to PNG using Sharp
  await sharp(Buffer.from(svgString))
    .png()
    .toFile(filename);

  return filename;
}

// Usage: Rasterize icon before using in HTML
const iconPath = await rasterizeIconPng(FaHome, "4472c4", "256", "home-icon.png");
// Then reference in HTML: <img src="home-icon.png" style="width: 40pt; height: 40pt;">
```

**Rasterizing Gradients with Sharp:**

```javascript
const sharp = require('sharp');

async function createGradientBackground(filename) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="562.5">
    <defs>
      <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" style="stop-color:#COLOR1"/>
        <stop offset="100%" style="stop-color:#COLOR2"/>
      </linearGradient>
    </defs>
    <rect width="100%" height="100%" fill="url(#g)"/>
  </svg>`;

  await sharp(Buffer.from(svg))
    .png()
    .toFile(filename);

  return filename;
}

// Usage: Create gradient background before HTML
const bgPath = await createGradientBackground("gradient-bg.png");
// Then in HTML: <body style="background-image: url('gradient-bg.png');">
```

### Example

```html
<!DOCTYPE html>
<html>
<head>
<style>
html { background: #ffffff; }
body {
  width: 720pt; height: 405pt; margin: 0; padding: 0;
  background: #f5f5f5; font-family: Arial, sans-serif;
  display: flex;
}
.content { margin: 30pt; padding: 40pt; background: #ffffff; border-radius: 8pt; }
h1 { color: #2d3748; font-size: 32pt; }
.box {
  background: #70ad47; padding: 20pt; border: 3px solid #5a8f37;
  border-radius: 12pt; box-shadow: 3px 3px 10px rgba(0, 0, 0, 0.25);
}
</style>
</head>
<body>
<div class="content">
  <h1>Recipe Title</h1>
  <ul>
    <li><b>Item:</b> Description</li>
  </ul>
  <p>Text with <b>bold</b>, <i>italic</i>, <u>underline</u>.</p>
  <!-- Faint background + label so HTML-screenshot shows it as a reserved area, not a blank gap. -->
  <div id="chart" class="placeholder"
       style="width: 350pt; height: 200pt; background: #f3f4f6; border: 1pt dashed #cbd5e1;
              display: flex; align-items: center; justify-content: center; color: #94a3b8;">
    <p style="font-size: 10pt;">[Chart placeholder]</p>
  </div>

  <!-- Text MUST be in <p> tags -->
  <div class="box">
    <p>5</p>
  </div>
</div>
</body>
</html>
```

## Using the html2pptx Library

Globally installed deps: `pptxgenjs`, `playwright`, `sharp`.

### API Reference

```javascript
await html2pptx(htmlFile, pres, options)
```

**Parameters**:
- `htmlFile` (string) — path to HTML (absolute or relative)
- `pres` (pptxgen) — PptxGenJS instance with layout already set
- `options` (object, optional):
  - `tmpDir` (string) — temp dir for generated files (default `process.env.TMPDIR || '/tmp'`)
  - `slide` (object) — existing slide to reuse (default: creates new)

**Returns**:
```javascript
{
  slide: pptxgenSlide,
  placeholders: [
    { id: string, x: number, y: number, w: number, h: number },
    ...
  ]
}
```

### Validation

The library collects ALL errors before throwing — fix them in **one batch of edits** before re-running:

1. HTML dimensions must match the presentation layout
2. Content must not overflow body (reports exact measurements)
3. CSS gradients are flagged
4. Backgrounds/borders/shadows on text elements are flagged (allowed only on divs)

### Working with Placeholders

```javascript
const { slide, placeholders } = await html2pptx('slide.html', pptx);

slide.addChart(pptx.charts.BAR, data, placeholders[0]);          // by index
const chartArea = placeholders.find(p => p.id === 'chart-area'); // by ID
slide.addChart(pptx.charts.LINE, data, chartArea);
slide.addTable(rows, placeholders[1]);                            // tables: same pattern
```

### Complete Example

Two rules — non-negotiable:

1. **Batch validate**: wrap each slide in `try...catch`, collect errors, throw once. Avoids the build → fix-1 → build → fix-2 loop.
2. **Always release Chromium** via `.finally(() => html2pptx.close())` — otherwise `writeFile()` errors hang the build until killed.

This is the canonical build script. Slide-specific chart/table additions go **inside the loop**, right after `html2pptx()` returns placeholders (gate by file name as needed).

```javascript
const pptxgen = require('pptxgenjs');
const html2pptx = require('./html2pptx');

async function main() {
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_16x9';  // Must match HTML body dimensions
  pptx.author = 'Your Name';
  pptx.title = 'My Presentation';

  const slides = ['slides/title.html', 'slides/data.html'];

  const failures = [];
  for (const file of slides) {
    try {
      const { slide, placeholders } = await html2pptx(file, pptx);

      // Slide-specific dynamic content gated by file name.
      if (file === 'slides/data.html') {
        const chartData = [{
          name: 'Sales',
          labels: ['Q1', 'Q2', 'Q3', 'Q4'],
          values: [4500, 5500, 6200, 7100]
        }];
        slide.addChart(pptx.charts.BAR, chartData, {
          ...placeholders[0],
          showTitle: true, title: 'Quarterly Sales',
          showCatAxisTitle: true, catAxisTitle: 'Quarter',
          showValAxisTitle: true, valAxisTitle: 'Sales ($000s)'
        });

        // Native table in the second placeholder
        const tableRows = [
          [{ text: 'Quarter', options: { bold: true } }, { text: 'Sales', options: { bold: true } }],
          ['Q1', '4500'], ['Q2', '5500'], ['Q3', '6200'], ['Q4', '7100']
        ];
        slide.addTable(tableRows, { ...placeholders[1], fontSize: 10, border: { type: 'solid', pt: 0.5 } });
      }
    } catch (err) {
      failures.push(`[${file}] ${err.message}`);
    }
  }

  if (failures.length) {
    throw new Error(
      `BUILD FAILED — ${failures.length}/${slides.length} slide(s) invalid:\n${failures.join('\n')}`
    );
  }

  await pptx.writeFile({ fileName: 'output.pptx' });
  console.log(`Built ${slides.length} slide(s).`);
}

main()
  .catch(err => { console.error(err.message || err); process.exitCode = 1; })
  .finally(() => html2pptx.close());   // ALWAYS release the shared Chromium
```

> If you don't need dynamic charts/tables, omit the `if (file === ...)` block — `html2pptx()` alone produces a complete slide from the HTML.

## Using PptxGenJS

After converting HTML to slides with `html2pptx`, you'll use PptxGenJS to add dynamic content like tables, charts, images, and additional elements.

### ⚠️ Critical Rules

#### Colors
- **NEVER use `#` prefix** with hex colors in PptxGenJS - causes file corruption
- ✅ Correct: `color: "FF0000"`, `fill: { color: "0066CC" }`
- ❌ Wrong: `color: "#FF0000"` (breaks document)

### Adding Images

Always calculate aspect ratios from actual image dimensions:

```javascript
// Get image dimensions: identify image.png | grep -o '[0-9]* x [0-9]*'
const imgWidth = 1860, imgHeight = 1519;  // From actual file
const aspectRatio = imgWidth / imgHeight;

const h = 3;  // Max height
const w = h * aspectRatio;
const x = (10 - w) / 2;  // Center on 16:9 slide

slide.addImage({ path: "chart.png", x, y: 1.5, w, h });
```

### Adding Text

```javascript
// Rich text with formatting
slide.addText([
    { text: "Bold ", options: { bold: true } },
    { text: "Italic ", options: { italic: true } },
    { text: "Normal" }
], {
    x: 1, y: 2, w: 8, h: 1
});
```

### Adding Shapes

```javascript
// Rectangle
slide.addShape(pptx.shapes.RECTANGLE, {
    x: 1, y: 1, w: 3, h: 2,
    fill: { color: "4472C4" },
    line: { color: "000000", width: 2 }
});

// Circle
slide.addShape(pptx.shapes.OVAL, {
    x: 5, y: 1, w: 2, h: 2,
    fill: { color: "ED7D31" }
});

// Rounded rectangle
slide.addShape(pptx.shapes.ROUNDED_RECTANGLE, {
    x: 1, y: 4, w: 3, h: 1.5,
    fill: { color: "70AD47" },
    rectRadius: 0.2
});
```

### Adding Charts

**Required for most charts**: axis labels via `catAxisTitle` (category) and `valAxisTitle` (value).

**Data format**: pass an array of series; each series is `{ name, labels, values }`. Labels define the X-axis. Each series → one legend entry. Use a single series for simple bar/line charts.

**Time Series — choose correct granularity** (charts with only 1 point usually mean wrong aggregation):
- **< 30 days**: daily (e.g., "10-01", "10-02")
- **30–365 days**: monthly (e.g., "2024-01")
- **> 365 days**: yearly (e.g., "2024")

**Chart colors**: align with your design palette, with strong inter-series contrast, readability against slide background, and accessibility (avoid red-green only). Pass via `chartColors` (no `#` prefix).

#### Bar Chart (single-series with full options)

```javascript
const { slide, placeholders } = await html2pptx('slide.html', pptx);

slide.addChart(pptx.charts.BAR, [{
    name: "Sales 2024",
    labels: ["Q1", "Q2", "Q3", "Q4"],
    values: [4500, 5500, 6200, 7100]
}], {
    ...placeholders[0],  // placeholder position
    barDir: 'col',       // 'col' = vertical, 'bar' = horizontal
    showTitle: true, title: 'Quarterly Sales',
    showLegend: false,   // not needed for single series
    // Axis labels (required)
    showCatAxisTitle: true, catAxisTitle: 'Quarter',
    showValAxisTitle: true, valAxisTitle: 'Sales ($000s)',
    // Axis scaling — for clustered data (e.g. 4500-7100) start min closer to min value
    valAxisMinVal: 0, valAxisMaxVal: 8000,
    valAxisMajorUnit: 2000,    // y-label spacing
    catAxisLabelRotate: 45,    // rotate if crowded
    dataLabelPosition: 'outEnd',
    dataLabelColor: '000000',
    chartColors: ["4472C4"]    // single color for single-series
});
```

#### Line Chart

```javascript
slide.addChart(pptx.charts.LINE, [{
    name: "Temperature",
    labels: ["Jan", "Feb", "Mar", "Apr"],
    values: [32, 35, 42, 55]
}], {
    x: 1, y: 1, w: 8, h: 4,
    lineSize: 4, lineSmooth: true,
    showCatAxisTitle: true, catAxisTitle: 'Month',
    showValAxisTitle: true, valAxisTitle: 'Temperature (°F)',
    valAxisMinVal: 0, valAxisMaxVal: 60, valAxisMajorUnit: 20,
    // For data clustered in a range (e.g. 32-55), prefer valAxisMinVal closer to min to show variation
    chartColors: ["4472C4", "ED7D31", "A5A5A5"]
});
```

#### Pie Chart (no axis labels)

**Single series only** — all categories in `labels`, values in `values`.

```javascript
slide.addChart(pptx.charts.PIE, [{
    name: "Market Share",
    labels: ["Product A", "Product B", "Other"],
    values: [35, 45, 20]
}], {
    x: 2, y: 1, w: 6, h: 4,
    showPercent: true, showLegend: true, legendPos: 'r',
    chartColors: ["4472C4", "ED7D31", "A5A5A5"]
});
```

#### Scatter Chart (unusual data format)

**First series = X values; subsequent series = Y values only**:

```javascript
const data1 = [{ x: 10, y: 20 }, { x: 15, y: 25 }, { x: 20, y: 30 }];
const data2 = [{ x: 12, y: 18 }, { x: 18, y: 22 }];
const allXValues = [...data1.map(d => d.x), ...data2.map(d => d.x)];

slide.addChart(pptx.charts.SCATTER, [
    { name: 'X-Axis', values: allXValues },              // X values
    { name: 'Series 1', values: data1.map(d => d.y) },   // Y values
    { name: 'Series 2', values: data2.map(d => d.y) }
], {
    x: 1, y: 1, w: 8, h: 4,
    lineSize: 0,                  // 0 = no connecting lines
    lineDataSymbol: 'circle', lineDataSymbolSize: 6,
    showCatAxisTitle: true, catAxisTitle: 'X Axis',
    showValAxisTitle: true, valAxisTitle: 'Y Axis',
    chartColors: ["4472C4", "ED7D31"]
});
```

#### Multiple Data Series

Pass multiple series objects — one color per series in `chartColors`.

```javascript
slide.addChart(pptx.charts.LINE, [
    { name: "Product A", labels: ["Q1", "Q2", "Q3", "Q4"], values: [10, 20, 30, 40] },
    { name: "Product B", labels: ["Q1", "Q2", "Q3", "Q4"], values: [15, 25, 20, 35] }
], {
    x: 1, y: 1, w: 8, h: 4,
    showCatAxisTitle: true, catAxisTitle: 'Quarter',
    showValAxisTitle: true, valAxisTitle: 'Revenue ($M)',
    chartColors: ["16A085", "FF6B9D"]   // one color per series
});
```

### Adding Tables

**Common table options**: `x, y, w, h` (position/size in inches) · `colW` / `rowH` (arrays in inches) · `border: { pt, color }` · `fill: { color }` (no `#`) · `align: "left"|"center"|"right"` · `valign: "top"|"middle"|"bottom"` · `fontSize` · `autoPage` (auto-create slides on overflow).

#### Basic Table

```javascript
slide.addTable([
    ["Header 1", "Header 2", "Header 3"],
    ["Row 1, Col 1", "Row 1, Col 2", "Row 1, Col 3"],
    ["Row 2, Col 1", "Row 2, Col 2", "Row 2, Col 3"]
], {
    x: 0.5, y: 1, w: 9, h: 3,
    border: { pt: 1, color: "999999" },
    fill: { color: "F1F1F1" }
});
```

#### Table with Custom Formatting (per-cell styles via `{ text, options }`)

```javascript
const tableData = [
    // Header row with custom styling
    [
        { text: "Product", options: { fill: { color: "4472C4" }, color: "FFFFFF", bold: true } },
        { text: "Revenue", options: { fill: { color: "4472C4" }, color: "FFFFFF", bold: true } },
        { text: "Growth",  options: { fill: { color: "4472C4" }, color: "FFFFFF", bold: true } }
    ],
    ["Product A", "$50M", "+15%"],
    ["Product B", "$35M", "+22%"],
    ["Product C", "$28M", "+8%"]
];

slide.addTable(tableData, {
    x: 1, y: 1.5, w: 8, h: 3,
    colW: [3, 2.5, 2.5],
    rowH: [0.5, 0.6, 0.6, 0.6],
    border: { pt: 1, color: "CCCCCC" },
    align: "center", valign: "middle",
    fontSize: 14
});
```

#### Table with Merged Cells (`colspan` / `rowspan`)

```javascript
const mergedTableData = [
    [
        { text: "Q1 Results", options: { colspan: 3, fill: { color: "4472C4" }, color: "FFFFFF", bold: true } }
    ],
    ["Product", "Sales", "Market Share"],
    ["Product A", "$25M", "35%"],
    ["Product B", "$18M", "25%"]
];

slide.addTable(mergedTableData, {
    x: 1, y: 1, w: 8, h: 2.5,
    colW: [3, 2.5, 2.5],
    border: { pt: 1, color: "DDDDDD" }
});
```