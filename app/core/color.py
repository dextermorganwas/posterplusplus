from __future__ import annotations
import colorsys
import numpy as np
from PIL import Image, ImageStat


def _lum(rgb):
    r,g,b = [v/255 for v in rgb]
    return 0.2126*r + 0.7152*g + 0.0722*b


def dominant_sash_color(image: Image.Image, dark_threshold=0.17, force_gray_on_dark=True) -> tuple[tuple[int,int,int], tuple[int,int,int]]:
    im = image.convert("RGB")
    w,h = im.size
    # Sample artwork, not the lower strip where an existing status bar may sit.
    crop = im.crop((0, int(h*0.05), w, int(h*0.86))).resize((80, 120))
    pal = crop.quantize(colors=32, method=Image.Quantize.MEDIANCUT).convert("RGB")
    arr = np.asarray(pal).reshape(-1,3)
    best = None
    for rgb in arr:
        lum = _lum(rgb)
        mx,mn = max(rgb),min(rgb)
        sat = 0 if mx == 0 else (mx-mn)/mx
        # Hue-aware anti-skin heuristic; don't let faces become the whole sash.
        h_, s_, v_ = colorsys.rgb_to_hsv(*(c/255 for c in rgb))
        skin = (0.01 <= h_ <= 0.13 and 0.20 <= s_ <= 0.80 and v_ >= 0.35)
        score = (1.0 + sat*1.25) * (1.0 - abs(lum-0.45))
        if skin: score *= 0.35
        if best is None or score > best[0]: best=(score, tuple(int(c) for c in rgb))
    rgb = best[1]
    if _lum(rgb) <= dark_threshold and force_gray_on_dark:
        rgb = (58,58,62)
    else:
        # Keep saturated art-derived colour, but normalize brightness for a sash.
        r,g,b = [c/255 for c in rgb]
        hh,ss,ll = colorsys.rgb_to_hsv(r,g,b)[0], colorsys.rgb_to_hsv(r,g,b)[1], colorsys.rgb_to_hsv(r,g,b)[2]
        target_v = 0.34 if _lum(rgb) < 0.42 else 0.28
        hh = colorsys.rgb_to_hsv(r,g,b)[0]
        out = colorsys.hsv_to_rgb(hh, min(0.78, max(0.18, ss)), target_v)
        rgb = tuple(round(c*255) for c in out)
    text = (255,255,255) if _lum(rgb) < 0.58 else (18,18,20)
    return rgb, text
