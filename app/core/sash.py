from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont
import os


def _font_path() -> str:
    return "/usr/share/fonts/truetype/lato/Lato-Bold.ttf"


def _font_fixed(text: str, size: int):
    """Return one fixed-size font for every sash label.

    The font is Lato Bold, a clean Arial-like sans-serif chosen
    to match the simple, broad uppercase typography of the reference sash while
    keeping glyph proportions natural (no horizontal scaling).

    Sash labels intentionally share one typographic scale. We do not shrink
    individual labels just because they are longer; that makes labels such as
    VENICE WINNER / EMMY WINNER look smaller than TOP RATED.
    """
    return ImageFont.truetype(_font_path(), size)


def _text_width(font, text: str) -> float:
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    return float(probe.textlength(text, font=font))


def _draw_centered_text(draw, center_x: float, baseline: float, text: str, font, fill):
    width = _text_width(font, text)
    draw.text((center_x - width / 2, baseline), text, font=font, fill=fill, anchor="ls")


def draw_status_sash(image: Image.Image, label: str, color: tuple[int, int, int], text_color: tuple[int, int, int], settings) -> Image.Image:
    img = image.convert("RGBA").copy()
    w, h = img.size
    line_h = max(4, round(w * settings.sash_bottom_line_ratio))
    tab_h = max(line_h * 2, round(w * settings.sash_tab_height_ratio))
    radius = max(4, round(w * settings.sash_tab_radius_ratio))

    text = label.upper()
    try:
        # One font size for every sash label. This is deliberately not a
        # "fit-to-width" calculation: longer labels should not become smaller.
        font_size = max(16, round(w * settings.sash_font_ratio))
    except AttributeError:
        font_size = max(16, round(w * 0.044))

    try:
        pad_x = max(4, round(w * settings.sash_side_pad_ratio))
        tab_w = max(1, round(w * settings.sash_tab_width_ratio))
        tab_w = min(tab_w, w - 2 * line_h)
        font = _font_fixed(text, font_size)
        text_w = _text_width(font, text)
        # Keep a real horizontal safety margin inside the fixed-width tab.
        # The font size stays fixed across labels; the tab is intentionally
        # wide enough that long labels do not touch its rounded edges.
        if text_w > tab_w - (2 * pad_x):
            raise ValueError("sash label does not fit fixed tab with configured padding")
    except Exception:
        font = ImageFont.load_default()
        text_w = max(1, int(font.getlength(text))) if hasattr(font, 'getlength') else 1

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    bottom_inset = max(1, round(w * settings.sash_bottom_inset_ratio))
    bottom = h - bottom_inset
    y_line = bottom - line_h
    d.rectangle((0, y_line, w, h), fill=(*color, 255))

    x0 = (w - tab_w) // 2
    x1 = x0 + tab_w
    y0 = bottom - tab_h
    d.rounded_rectangle((x0, y0, x1, bottom), radius=radius, fill=(*color, 255))
    d.rectangle((x0, bottom - radius, x1, bottom), fill=(*color, 255))

    bbox = font.getbbox(text, anchor="ls")
    ascent, descent = font.getmetrics() if hasattr(font, 'getmetrics') else (font.size, 0)
    # Center the full font metrics in the tab, not the label's individual ink
    # box. Every label therefore shares the exact same baseline.
    center_y = y0 + tab_h / 2
    baseline = center_y + (ascent - descent) / 2 + (w * settings.sash_text_vertical_offset_ratio)
    baseline_local = round(baseline)
    td = ImageDraw.Draw(layer)
    _draw_centered_text(td, x0 + tab_w / 2 + 1, baseline_local + 1, text, font, (0, 0, 0, 75))
    _draw_centered_text(td, x0 + tab_w / 2, baseline_local, text, font, (*text_color, 255))
    return Image.alpha_composite(img, layer).convert("RGB")
