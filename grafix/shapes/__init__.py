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
    raise ValueError(f"Nieznany typ: {t}")


__all__ = ["Shape", "Line", "Rect", "Circle", "shape_from_dict"]
