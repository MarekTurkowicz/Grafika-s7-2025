from dataclasses import dataclass
import math
from ..algos import bresenham_circle
from ..constants import COL_CIRC
from ..utils import parts
from .base import Shape, OidMixin


@dataclass
class Circle(Shape, OidMixin):
    cx: int
    cy: int
    r: int
    oid: str = ""

    def __post_init__(self):
        if not self.oid:
            self.oid = self._new_oid()

    def _draw_pixels(self, surface):
        surface.clear_tag(self.oid)
        tags = ("shape", self.oid, "circle")
        for x, y in bresenham_circle(int(self.cx), int(self.cy), int(self.r)):
            surface.plot(x, y, COL_CIRC, tags)
        surface.flush()

    def draw(self, surface, canvas):
        self._draw_pixels(surface)

    def update_canvas(self, surface, canvas):
        self._draw_pixels(surface)

    def move(self, dx, dy):
        self.cx += dx
        self.cy += dy

    def handles(self):
        return [(self.cx, self.cy, "center"), (self.cx + self.r, self.cy, "radius")]

    def apply_handle(self, kind, x, y):
        if kind == "center":
            self.cx, self.cy = x, y
        elif kind == "radius":
            self.r = max(1, int(round(math.hypot(x - self.cx, y - self.cy))))

    def params_text(self):
        return f"{self.cx},{self.cy},{self.r}"

    def set_params_text(self, txt):
        cx, cy, r = map(int, parts(txt, 3))
        if r <= 0:
            raise ValueError("Promień musi być > 0")
        self.cx, self.cy, self.r = cx, cy, r

    def to_dict(self):
        return {"type": "circle", "cx": self.cx, "cy": self.cy, "r": self.r}

    def bbox(self):
        return (self.cx - self.r, self.cy - self.r, self.cx + self.r, self.cy + self.r)
