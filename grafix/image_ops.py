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


def _clamp_byte(v: float) -> int:
    v = int(round(v))
    if v < 0:
        return 0
    if v > 255:
        return 255
    return v


def add_constant(pixels, value):
    """Dodawanie stałej do wszystkich kanałów (z ograniczeniem 0..255)."""
    out = []
    for r, g, b in pixels:
        out.append(
            (
                _clamp_byte(r + value),
                _clamp_byte(g + value),
                _clamp_byte(b + value),
            )
        )
    return out


def mul_constant(pixels, value):
    """Mnożenie wszystkich kanałów przez stałą."""
    out = []
    for r, g, b in pixels:
        out.append(
            (
                _clamp_byte(r * value),
                _clamp_byte(g * value),
                _clamp_byte(b * value),
            )
        )
    return out


def div_constant(pixels, value):
    """Dzielenie wszystkich kanałów przez stałą (value != 0)."""
    if value == 0:
        raise ValueError("Dzielenie przez zero jest niedozwolone.")
    out = []
    for r, g, b in pixels:
        out.append(
            (
                _clamp_byte(r / value),
                _clamp_byte(g / value),
                _clamp_byte(b / value),
            )
        )
    return out


def change_brightness(pixels, delta):
    """Zmiana jasności – to samo co dodawanie, ale logicznie rozdzielone."""
    return add_constant(pixels, delta)


def to_grayscale_avg(pixels):
    """Skala szarości – prosty średni (R+G+B)/3."""
    out = []
    for r, g, b in pixels:
        gval = _clamp_byte((r + g + b) / 3.0)
        out.append((gval, gval, gval))
    return out


def to_grayscale_luma(pixels):
    """Skala szarości – ważona luminancja (0.299R + 0.587G + 0.114B)."""
    out = []
    for r, g, b in pixels:
        gval = _clamp_byte(0.299 * r + 0.587 * g + 0.114 * b)
        out.append((gval, gval, gval))
    return out
