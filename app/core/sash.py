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
    y_line = h-line_h
    d.rectangle((0, y_line, w, h), fill=(*color, 255))
    bbox = d.textbbox((0,0), label, font=font)
    tw = bbox[2]-bbox[0]
    th = bbox[3]-bbox[1]
    min_tab_w = max(2 * line_h, round(w * settings.sash_min_tab_width_ratio))
    max_tab_w = min(w-2*line_h, round(w * settings.sash_max_tab_width_ratio))
    tab_w = max(min_tab_w, min(max_tab_w, tw + 2*pad_x))
    x0 = (w-tab_w)//2
    x1 = x0+tab_w
    y0 = h-tab_h
    # The shape is the core inspiration from the attached examples: a thin full
    # width rail with a centered upward tab and smoothly rounded top shoulders.
    d.rounded_rectangle((x0, y0, x1, h), radius=radius, fill=(*color,255))
    d.rectangle((x0, h-radius, x1, h), fill=(*color,255))
    tx = x0 + (tab_w-tw)//2 - bbox[0]
    ty = y0 + max(1, (tab_h-th)//2) - bbox[1] - 1
    # tiny shadow keeps white type crisp on highly saturated art
    d.text((tx+1,ty+1), label, font=font, fill=(0,0,0,75))
    d.text((tx,ty), label, font=font, fill=(*text_color,255))
    return Image.alpha_composite(img, layer).convert("RGB")
