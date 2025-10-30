# grafix/image_ops.py
from typing import List, Tuple

Color = Tuple[int, int, int]


def clamp(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def linear_color_scale(pixels: List[Color], in_min: int, in_max: int) -> List[Color]:
    in_min = max(0, min(255, int(in_min)))
    in_max = max(0, min(255, int(in_max)))
    if in_max <= in_min:
        return pixels[:]  # brak zmian
    k = 255.0 / (in_max - in_min)
    out: List[Color] = []
    for r, g, b in pixels:
        rr = clamp(int(round((r - in_min) * k)))
        gg = clamp(int(round((g - in_min) * k)))
        bb = clamp(int(round((b - in_min) * k)))
        out.append((rr, gg, bb))
    return out
