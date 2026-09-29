#!/usr/bin/env python3
"""
generate_badge.py — Clean SVG badge generator.

Creates high-quality, scalable SVG badges for GitHub READMEs.
Supports custom background colors, automatic contrast calculation,
vector SVG logos, and multiple corner styles (pill, rounded, flat).
"""

import argparse
import html
import os
import re
import sys
import xml.etree.ElementTree as ET

from PIL import ImageFont

ET.register_namespace("", "http://www.w3.org/2000/svg")


def hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    """Convert hex color code (#RGB or #RRGGBB) to (R, G, B) tuple."""
    hex_code = hex_code.strip().lstrip("#")
    if len(hex_code) == 3:
        hex_code = "".join(c * 2 for c in hex_code)
    elif len(hex_code) != 6:
        return (32, 35, 42)
    return tuple(int(hex_code[i : i + 2], 16) for i in (0, 2, 4))


def get_contrast_text_color(bg_hex: str) -> str:
    """Calculate WCAG luminance: returns white or dark text for high contrast."""
    try:
        r, g, b = hex_to_rgb(bg_hex)

        def to_linear(c: int) -> float:
            c_norm = c / 255.0
            return c_norm / 12.92 if c_norm <= 0.03928 else ((c_norm + 0.055) / 1.055) ** 2.4

        luminance = 0.2126 * to_linear(r) + 0.7152 * to_linear(g) + 0.0722 * to_linear(b)
        return "#0f172a" if luminance > 0.46 else "#ffffff"
    except (ValueError, TypeError, IndexError):
        return "#ffffff"


def calculate_text_width(text: str, font_size: float = 11.0) -> float:
    """Measure exact text width in pixels using Pillow system fonts."""
    font_candidates = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]
    font = None
    for path in font_candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, int(font_size))
                break
            except OSError:
                pass

    if font is None:
        font = ImageFont.load_default()

    bbox = font.getbbox(text)
    return round(float(bbox[2] - bbox[0]) + 0.5, 1)


def parse_and_clean_svg_logo(logo_path: str, target_color: str = "#ffffff") -> tuple[str, str]:
    """Extract viewBox and inner elements from an SVG file, recoloring monochrome fills."""
    if not os.path.isfile(logo_path):
        raise FileNotFoundError(f"Logo file not found: {logo_path}")

    with open(logo_path, encoding="utf-8", errors="ignore") as f:
        content = f.read().strip()

    # Clean XML headers and comments
    content = re.sub(r"<\?xml[^>]*\?>", "", content)
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    content = re.sub(r"<title>.*?</title>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()

    root = ET.fromstring(content)
    view_box = root.attrib.get("viewBox")
    if not view_box:
        w = root.attrib.get("width", "24").replace("px", "").strip()
        h = root.attrib.get("height", "24").replace("px", "").strip()
        try:
            view_box = f"0 0 {int(float(w))} {int(float(h))}"
        except (ValueError, TypeError):
            view_box = "0 0 24 24"

    inner_parts = []
    for child in root:
        tag_name = child.tag.split("}")[-1].lower()
        if tag_name in ("title", "desc"):
            continue
        xml_str = ET.tostring(child, encoding="unicode")
        xml_str = re.sub(r'\s+xmlns(:\w+)?="[^"]*"', "", xml_str)
        inner_parts.append(xml_str)

    inner = "".join(inner_parts).strip()
    # Normalize monochrome fills and strokes to high-contrast target color
    inner = re.sub(
        r'(fill|stroke)=["\']currentcolor["\']',
        f'\\1="{target_color}"',
        inner,
        flags=re.IGNORECASE,
    )
    inner = re.sub(
        r'fill=["\'](?!none\b|transparent\b)[^"\']+["\']',
        f'fill="{target_color}"',
        inner,
        flags=re.IGNORECASE,
    )
    return view_box, inner


def generate_badge_svg(
    text: str,
    logo_path: str | None = None,
    bg_color: str = "#20232A",
    output_path: str | None = None,
    style: str = "pill",
    height: int = 28,
    logo_size: int = 14,
) -> str:
    """Generate SVG badge markup with symmetrical margins and auto-contrast."""
    text_color = get_contrast_text_color(bg_color)
    rx = round(height / 2.0, 1) if style == "pill" else (6.0 if style == "rounded" else 0.0)
    pad = 10.0 if style == "pill" else 9.0
    gap = 6.0

    text_w = calculate_text_width(text)
    logo_tag = ""
    text_x = pad

    if logo_path:
        try:
            view_box, inner = parse_and_clean_svg_logo(logo_path, text_color)
            logo_y = round((height - logo_size) / 2.0, 1)
            logo_tag = (
                f'<svg x="{pad}" y="{logo_y}" width="{logo_size}" height="{logo_size}" '
                f'viewBox="{view_box}" fill="{text_color}" aria-hidden="true">{inner}</svg>'
            )
            text_x = round(pad + logo_size + gap, 1)
        except Exception as e:
            sys.stderr.write(f"Warning: could not process logo ({e}), creating text-only badge.\n")

    total_width = round(text_x + text_w + pad, 1)
    text_y = round(height / 2.0, 1)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="{height}" viewBox="0 0 {total_width} {height}" role="img" aria-label="{html.escape(text)}">
  <title>{html.escape(text)}</title>
  <rect width="{total_width}" height="{height}" rx="{rx}" fill="{bg_color}" />
  {logo_tag}
  <text x="{text_x}" y="{text_y}" fill="{text_color}" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="11.0" font-weight="600" dominant-baseline="central">{html.escape(text)}</text>
</svg>
""".strip()

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg)

    return svg


def main():
    parser = argparse.ArgumentParser(
        description="Generate clean, modern SVG badges with vector logos."
    )
    parser.add_argument("text", help="Badge label text (e.g. 'React')")
    parser.add_argument("-l", "--logo", help="Path to local SVG logo file")
    parser.add_argument(
        "-c",
        "--color",
        default="#20232A",
        help="Background hex color (default: #20232A)",
    )
    parser.add_argument("-o", "--output", help="Output SVG file path (default: <slug>.svg)")
    parser.add_argument(
        "-s",
        "--style",
        choices=["pill", "rounded", "flat"],
        default="pill",
        help="Corner style (default: pill)",
    )
    parser.add_argument(
        "--stdout", action="store_true", help="Print SVG to stdout instead of saving to file"
    )

    args = parser.parse_args()
    output = args.output
    if not output and not args.stdout:
        slug = re.sub(r"[^a-zA-Z0-9_\-\.]+", "-", args.text.strip().lower()).strip("-")
        output = f"{slug}.svg"

    svg = generate_badge_svg(
        text=args.text,
        logo_path=args.logo,
        bg_color=args.color,
        output_path=None if args.stdout else output,
        style=args.style,
    )

    if args.stdout:
        print(svg)
    else:
        print(f"✓ Generated badge: {output}")


if __name__ == "__main__":
    main()
