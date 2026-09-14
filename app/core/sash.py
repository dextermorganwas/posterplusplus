from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os


def draw_status_sash(image: Image.Image, label: str, color: tuple[int,int,int], text_color: tuple[int,int,int], settings) -> Image.Image:
    img = image.convert("RGBA").copy()
    w,h = img.size
    line_h = max(4, round(w*settings.sash_bottom_line_ratio))
    tab_h = max(line_h*2, round(w*settings.sash_tab_height_ratio))
    radius = max(4, round(w*settings.sash_tab_radius_ratio))
    font_size = max(16, round(w*settings.sash_font_ratio))
    pad_x = max(8, round(w*settings.sash_side_pad_ratio))

    try:
        font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Inter-Bold.ttf")
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    layer = Image.new("RGBA", (w, h), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    # Keep the entire sash inside a consistent bottom-safe region. Stremio commonly
    # applies a rounded mask to poster cards, so drawing flush to the bitmap edge
    # can clip the rail differently depending on the source poster's dimensions.
    bottom_inset = max(1, round(w * settings.sash_bottom_inset_ratio))
    bottom = h - bottom_inset
    y_line = bottom-line_h
    # Paint the entire lower safe region through the bitmap edge. This prevents
    # any source-poster pixels from peeking out below the sash when a client applies
    # a crop/mask with slightly different edge rounding. The visible rail thickness
    # is still controlled by sash_bottom_line_ratio; the extra bottom inset becomes
    # color fill rather than exposed poster art.
    d.rectangle((0, y_line, w, h), fill=(*color, 255))
    bbox = d.textbbox((0,0), label, font=font)
    tw = bbox[2]-bbox[0]
    th = bbox[3]-bbox[1]
    ascent, descent = font.getmetrics()
    min_tab_w = max(2 * line_h, round(w * settings.sash_min_tab_width_ratio))
    max_tab_w = min(w-2*line_h, round(w * settings.sash_max_tab_width_ratio))
    tab_w = max(min_tab_w, min(max_tab_w, tw + 2*pad_x))
    x0 = (w-tab_w)//2
    x1 = x0+tab_w
    y0 = bottom-tab_h
    # The shape is the core inspiration from the attached examples: a thin full
    # width rail with a centered upward tab and smoothly rounded top shoulders.
    d.rounded_rectangle((x0, y0, x1, bottom), radius=radius, fill=(*color,255))
    d.rectangle((x0, bottom-radius, x1, bottom), fill=(*color,255))
    tx = x0 + (tab_w-tw)//2 - bbox[0]
    # Use one fixed typographic baseline for every label instead of vertically
    # centering each label's glyph bounding box. Glyphs with descenders (for
    # example the "y" in "Today") otherwise produce a visibly different vertical
    # position from labels without descenders (such as "New").
    text_center_y = y0 + tab_h / 2
    baseline_y = round(text_center_y + (ascent - descent) / 2 + w * settings.sash_text_vertical_offset_ratio)
    # tiny shadow keeps white type crisp on highly saturated art
    d.text((tx+1, baseline_y+1), label, font=font, fill=(0,0,0,75), anchor='ls')
    d.text((tx, baseline_y), label, font=font, fill=(*text_color,255), anchor='ls')
    return Image.alpha_composite(img, layer).convert("RGB")
