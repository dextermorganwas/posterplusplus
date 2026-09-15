from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont
import os


def _font_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Inter-Bold.ttf")


def _font_that_fits(text: str, start_size: int, min_size: int, max_width: int):
    """Choose the largest natural-size font that fits; never horizontally squash glyphs."""
    size = max(min_size, start_size)
    while size > min_size:
        f = ImageFont.truetype(_font_path(), size)
        bbox = f.getbbox(text, anchor="ls")
        width = max(1, bbox[2] - bbox[0])
        if width <= max_width:
            return f, width
        size -= 1
    f = ImageFont.truetype(_font_path(), min_size)
    bbox = f.getbbox(text, anchor="ls")
    return f, max(1, bbox[2] - bbox[0])


def draw_status_sash(image: Image.Image, label: str, color: tuple[int, int, int], text_color: tuple[int, int, int], settings) -> Image.Image:
    img = image.convert("RGBA").copy()
    w, h = img.size
    line_h = max(4, round(w * settings.sash_bottom_line_ratio))
    tab_h = max(line_h * 2, round(w * settings.sash_tab_height_ratio))
    radius = max(4, round(w * settings.sash_tab_radius_ratio))

    try:
        text = label.upper()
        start_font_size = max(16, round(w * settings.sash_font_ratio))
        min_font_size = max(12, round(w * settings.sash_min_font_ratio))
    except AttributeError:
        text = label.upper()
        start_font_size = max(16, round(w * 0.052))
        min_font_size = max(12, round(w * 0.038))

    try:
        pad_x = max(8, round(w * settings.sash_side_pad_ratio))
        tab_w = max(1, round(w * settings.sash_tab_width_ratio))
        tab_w = min(tab_w, w - 2 * line_h)
        max_text_w = max(1, tab_w - 2 * pad_x)
        font, text_w = _font_that_fits(text, start_font_size, min_font_size, max_text_w)
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
    # Center the font's ascent/descent box in the tab. This gives every label the
    # same optical vertical placement without glyph-width/descender-dependent hacks.
    center_y = y0 + tab_h / 2
    baseline = center_y + (ascent - descent) / 2 + (w * settings.sash_text_vertical_offset_ratio)
    baseline_local = round(baseline)
    tx = x0 + (tab_w - text_w) / 2 - bbox[0]
    td = ImageDraw.Draw(layer)
    td.text((tx + 1, baseline_local + 1), text, font=font, fill=(0, 0, 0, 75), anchor="ls")
    td.text((tx, baseline_local), text, font=font, fill=(*text_color, 255), anchor="ls")
    return Image.alpha_composite(img, layer).convert("RGB")
