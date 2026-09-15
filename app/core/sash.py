from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont
import os


def _fit_uppercase_text(label: str, font: ImageFont.FreeTypeFont, max_width: int):
    """Render fixed-case text and horizontally fit it without changing its baseline math.

    The inspiration uses a consistent tab width and uppercase labels. We preserve one
    fixed typographic baseline for every label, while fitting the glyph run into the
    same tab width so label length never changes the sash geometry.
    """
    text = label.upper()
    bbox = font.getbbox(text, anchor="ls")
    tw = max(1, bbox[2] - bbox[0])
    th = max(1, bbox[3] - bbox[1])
    if tw <= max_width:
        return text, font, 1.0
    # Rather than reducing the font size independently per label (which changes the
    # visual vertical metrics), render at the configured size and apply only a small
    # horizontal compression. This keeps the text height/baseline consistent.
    return text, font, max_width / tw


def draw_status_sash(image: Image.Image, label: str, color: tuple[int,int,int], text_color: tuple[int,int,int], settings) -> Image.Image:
    img = image.convert("RGBA").copy()
    w, h = img.size
    line_h = max(4, round(w * settings.sash_bottom_line_ratio))
    tab_h = max(line_h * 2, round(w * settings.sash_tab_height_ratio))
    radius = max(4, round(w * settings.sash_tab_radius_ratio))
    font_size = max(16, round(w * settings.sash_font_ratio))

    try:
        font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Inter-Bold.ttf")
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    bottom_inset = max(1, round(w * settings.sash_bottom_inset_ratio))
    bottom = h - bottom_inset
    y_line = bottom - line_h
    d.rectangle((0, y_line, w, h), fill=(*color, 255))

    # Inspiration geometry: the tab is a fixed proportion of the poster, not a
    # function of label length. This keeps every sash visually identical in size.
    tab_w = max(1, round(w * settings.sash_tab_width_ratio))
    tab_w = min(tab_w, w - 2 * line_h)
    x0 = (w - tab_w) // 2
    x1 = x0 + tab_w
    y0 = bottom - tab_h
    d.rounded_rectangle((x0, y0, x1, bottom), radius=radius, fill=(*color, 255))
    d.rectangle((x0, bottom - radius, x1, bottom), fill=(*color, 255))

    # All labels are uppercased and share one font size/baseline. Width is fitted
    # horizontally only, so glyphs like Y no longer alter vertical placement.
    text = label.upper()
    pad_x = max(8, round(w * settings.sash_side_pad_ratio))
    max_text_w = max(1, tab_w - 2 * pad_x)
    text, font, scale_x = _fit_uppercase_text(text, font, max_text_w)
    bbox = d.textbbox((0, 0), text, font=font)
    tw = max(1, bbox[2] - bbox[0])

    text_img_w = tw + 4
    text_layer = Image.new("RGBA", (text_img_w, tab_h * 2), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)
    ascent, descent = font.getmetrics()
    # Fixed baseline relative to the tab. The small positive offset preserves the
    # subtle downward nudge from the previous tuned version.
    baseline_local = round(tab_h + w * settings.sash_text_vertical_offset_ratio)
    td.text((2 - bbox[0], baseline_local), text, font=font, fill=(*text_color, 255), anchor="ls")
    shadow = Image.new("RGBA", text_layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text((3 - bbox[0], baseline_local + 1), text, font=font, fill=(0, 0, 0, 75), anchor="ls")
    text_layer = Image.alpha_composite(shadow, text_layer)

    if scale_x < 1.0:
        new_w = max(1, round(text_layer.width * scale_x))
        text_layer = text_layer.resize((new_w, text_layer.height), Image.Resampling.LANCZOS)

    tx = x0 + (tab_w - text_layer.width) // 2
    ty = y0 + tab_h // 2 - text_layer.height // 2
    layer.alpha_composite(text_layer, (tx, ty))
    return Image.alpha_composite(img, layer).convert("RGB")
