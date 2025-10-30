from grafix.shapes.image import RasterImage
from .base import Shape
from .line import Line
from .rect import Rect
from .circle import Circle


def shape_from_dict(d: dict) -> Shape:
    t = d.get("type")
    if t == "line":
        return Line(d["x1"], d["y1"], d["x2"], d["y2"])
    if t == "rect":
        return Rect(d["x1"], d["y1"], d["x2"], d["y2"])
    if t == "circle":
        return Circle(d["cx"], d["cy"], d["r"])
    if t == "image":
        # wczytaj PPM jako źródło
        src = d.get("src")
        if src:
            try:
                from ..io.ppm import read_ppm_auto

                sw, sh, spx, _fmt = read_ppm_auto(src)
                # docelowe w/h (jeśli brak – 1:1)
                w = int(d.get("w", sw))
                h = int(d.get("h", sh))
                return RasterImage(
                    x=int(d.get("x", 0)),
                    y=int(d.get("y", 0)),
                    src_w=sw,
                    src_h=sh,
                    src_pixels=spx,
                    w=w,
                    h=h,
                    src=src,
                )
            except Exception:
                pass
        # fallback: „szary place-holder” jeśli nie ma src
        w = int(d.get("w", 64))
        h = int(d.get("h", 64))
        spx = [(200, 200, 200)] * (w * h)
        return RasterImage(
            x=int(d.get("x", 0)),
            y=int(d.get("y", 0)),
            src_w=w,
            src_h=h,
            src_pixels=spx,
            w=w,
            h=h,
            src=src,
        )

    raise ValueError(f"Nieznany typ: {t}")


__all__ = ["Shape", "Line", "Rect", "Circle", "RasterImage", "shape_from_dict"]
