from dataclasses import dataclass
from ..algos import bresenham_line
from ..constants import COL_RECT
from ..utils import parts
from .base import Shape, OidMixin


@dataclass
class Rect(Shape, OidMixin):
    x1: int
    y1: int
    x2: int
    y2: int
    oid: str = ""

    def __post_init__(self):
        if not self.oid:
            self.oid = self._new_oid()

    def _norm(self):
        self.x1, self.x2 = sorted([self.x1, self.x2])
        self.y1, self.y2 = sorted([self.y1, self.y2])

    def _draw_pixels(self, surface):
        surface.clear_tag(self.oid)
        self._norm()
        tags = ("shape", self.oid, "rect")
        pts = []
        pts += bresenham_line(self.x1, self.y1, self.x2, self.y1)
        pts += bresenham_line(self.x2, self.y1, self.x2, self.y2)
        pts += bresenham_line(self.x2, self.y2, self.x1, self.y2)
        pts += bresenham_line(self.x1, self.y2, self.x1, self.y1)
        for x, y in dict.fromkeys(pts):
            surface.plot(x, y, COL_RECT, tags)
        surface.flush()

    def draw(self, surface, canvas):
        self._draw_pixels(surface)

    def update_canvas(self, surface, canvas):
        self._draw_pixels(surface)

    def move(self, dx, dy):
        self.x1 += dx
        self.y1 += dy
        self.x2 += dx
        self.y2 += dy

    def handles(self):
        self._norm()
        return [
            (self.x1, self.y1, "tl"),
            (self.x2, self.y1, "tr"),
            (self.x2, self.y2, "br"),
            (self.x1, self.y2, "bl"),
        ]

    def apply_handle(self, kind, x, y):
        if kind == "tl":
            self.x1, self.y1 = x, y
        elif kind == "tr":
            self.x2, self.y1 = x, y
        elif kind == "br":
            self.x2, self.y2 = x, y
        elif kind == "bl":
            self.x1, self.y2 = x, y

    def params_text(self):
        return f"{self.x1},{self.y1},{self.x2},{self.y2}"

    def set_params_text(self, txt):
        x1, y1, x2, y2 = map(int, parts(txt, 4))
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self._norm()

    def to_dict(self):
        return {
            "type": "rect",
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        }

    def bbox(self):
        self._norm()
        return (self.x1, self.y1, self.x2, self.y2)
