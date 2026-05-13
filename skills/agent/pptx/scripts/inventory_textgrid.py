#!/usr/bin/env python3
"""
Render a PowerPoint deck as a structured plain-text "thumbnail grid".

This is the dependency-free fallback for visual analysis of an EXISTING .pptx
when neither LibreOffice (`soffice`) nor the html2pptx HTML sources are
available. It does NOT produce real pixels — instead it dumps every shape's
bbox / font / color / text and surfaces the overflow + overlap issues that
inventory.py already detects.

Use cases:
- Reading a template deck before re-creating it (the C2 case in the failure
  analysis): you lose visual fidelity but keep the layout skeleton, which is
  enough to write a similar deck.
- Machine-checking a freshly generated .pptx for "did anything spill off the
  slide / overlap another text frame" without screenshotting.

Output (Markdown, easy for an LLM to read):

    === Slide 0  (10.00 x 5.63 in)  shapes=4
    [shape-0] PLACEHOLDER:TITLE   bbox=(0.50, 0.50)-(9.50, 1.50) in
              font=Calibri 36pt color=#1F4E79 bold
              text="Quarterly Review"
    [shape-1] BODY                bbox=(0.50, 2.00)-(4.50, 5.00) in
              font=Calibri 14pt color=#333333
              text="• Revenue +12% ..." (3 paragraphs, 87 chars)
    !! shape-1: text overflows frame by 0.40 in (estimated)
    !! shape-2 overlaps shape-1: 1.20 sq in

Usage:
    python inventory_textgrid.py input.pptx [-o report.md]
    python inventory_textgrid.py input.pptx --issues-only   # only flag problems
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from inventory import extract_text_inventory
from pptx import Presentation


def _color_str(shape_data) -> str:
    """Pick a representative color for the shape (first paragraph's first run)."""
    try:
        for p in shape_data.paragraphs:
            for r in getattr(p, "runs", []) or []:
                color = getattr(r, "color", None)
                if color:
                    return str(color)
    except Exception:
        pass
    return "?"


def _font_str(shape_data) -> str:
    """Pick a representative font: first paragraph's first run."""
    try:
        for p in shape_data.paragraphs:
            font_name = getattr(p, "font_name", None) or "?"
            font_size = getattr(p, "font_size", None) or "?"
            bold = getattr(p, "bold", False)
            extra = " bold" if bold else ""
            return f"{font_name} {font_size}pt{extra}"
    except Exception:
        pass
    return "? ?pt"


def _text_summary(shape_data, max_chars: int = 80) -> str:
    """Return a short text preview plus paragraph/character counts."""
    paragraphs = []
    total_chars = 0
    try:
        for p in shape_data.paragraphs:
            txt = getattr(p, "text", "") or ""
            paragraphs.append(txt)
            total_chars += len(txt)
    except Exception:
        pass
    if not paragraphs:
        return '""'
    joined = " / ".join(paragraphs)
    preview = joined if len(joined) <= max_chars else joined[:max_chars] + "..."
    suffix = ""
    if len(paragraphs) > 1 or total_chars > max_chars:
        suffix = f" ({len(paragraphs)} paragraphs, {total_chars} chars)"
    return f'"{preview}"{suffix}'


def _shape_kind(shape_data) -> str:
    if shape_data.placeholder_type:
        return f"PLACEHOLDER:{shape_data.placeholder_type}"
    # Try to infer from the underlying pptx shape object
    try:
        st = shape_data.shape.shape_type
        return str(st).split(".")[-1].split(" ")[0]
    except Exception:
        return "SHAPE"


def render_textgrid(pptx_path: Path, issues_only: bool = False) -> str:
    prs = Presentation(str(pptx_path))
    sw_in = (prs.slide_width or 9144000) / 914400.0
    sh_in = (prs.slide_height or 5143500) / 914400.0
    inventory = extract_text_inventory(pptx_path, prs, issues_only=issues_only)

    lines: list[str] = []
    lines.append(f"# Text-grid preview of {pptx_path.name}")
    lines.append(
        f"Slide size: {sw_in:.2f} x {sh_in:.2f} in. "
        f"Slides shown: {len(inventory)}"
        + ("  (issues-only)" if issues_only else "")
    )
    lines.append("")

    if not inventory:
        lines.append("(no slides / no text shapes found)")
        return "\n".join(lines)

    for slide_key in sorted(inventory.keys(), key=lambda s: int(s.split("-")[1])):
        shapes = inventory[slide_key]
        slide_idx = int(slide_key.split("-")[1])
        lines.append(f"=== Slide {slide_idx}  shapes={len(shapes)} ===")

        for shape_id, sd in shapes.items():
            kind = _shape_kind(sd)
            right = sd.left + sd.width
            bottom = sd.top + sd.height
            lines.append(
                f"[{shape_id}] {kind}  "
                f"bbox=({sd.left:.2f}, {sd.top:.2f})-({right:.2f}, {bottom:.2f}) in"
            )
            lines.append(f"           font={_font_str(sd)} color={_color_str(sd)}")
            lines.append(f"           text={_text_summary(sd)}")

            # Inline issues from inventory's existing detection
            if sd.slide_overflow_right and sd.slide_overflow_right > 0:
                lines.append(
                    f"  !! {shape_id} extends past slide right edge by "
                    f"{sd.slide_overflow_right:.2f} in"
                )
            if sd.slide_overflow_bottom and sd.slide_overflow_bottom > 0:
                lines.append(
                    f"  !! {shape_id} extends past slide bottom edge by "
                    f"{sd.slide_overflow_bottom:.2f} in"
                )
            if sd.frame_overflow_bottom and sd.frame_overflow_bottom > 0:
                lines.append(
                    f"  !! {shape_id} text overflows its frame by "
                    f"~{sd.frame_overflow_bottom:.2f} in (estimated)"
                )
            for other_id, area in sd.overlapping_shapes.items():
                lines.append(
                    f"  !! {shape_id} overlaps {other_id}: ~{area:.2f} sq in"
                )
            for w in sd.warnings:
                lines.append(f"  !! {shape_id}: {w}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Render a .pptx as a structured plain-text 'thumbnail grid'."
    )
    ap.add_argument("input", help="Input .pptx file")
    ap.add_argument(
        "-o",
        "--output",
        help="Output Markdown file (default: stdout)",
        default=None,
    )
    ap.add_argument(
        "--issues-only",
        action="store_true",
        help="Only include shapes with overflow / overlap issues.",
    )
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists() or in_path.suffix.lower() != ".pptx":
        print(f"Error: not a readable .pptx file: {args.input}", file=sys.stderr)
        sys.exit(1)

    text = render_textgrid(in_path, issues_only=args.issues_only)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"Wrote text-grid preview to: {out}")
    else:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")


if __name__ == "__main__":
    main()
