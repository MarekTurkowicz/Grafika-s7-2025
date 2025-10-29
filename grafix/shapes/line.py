from dataclasses import dataclass
from ..algos import bresenham_line
from ..constants import COL_LINE
from ..utils import parts
from .base import Shape, OidMixin


@dataclass
class Line(Shape, OidMixin):
    x1: int
    y1: int
    x2: int
    y2: int
    oid: str = ""

    def __post_init__(self):
        if not self.oid:
            self.oid = self._new_oid()

    def _draw_pixels(self, surface):
        surface.clear_tag(self.oid)
        tags = ("shape", self.oid, "line")
        for x, y in bresenham_line(
            int(self.x1), int(self.y1), int(self.x2), int(self.y2)
        ):
            surface.plot(x, y, COL_LINE, tags)
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
        return [(self.x1, self.y1, "p1"), (self.x2, self.y2, "p2")]

    def apply_handle(self, kind, x, y):
        if kind == "p1":
            self.x1, self.y1 = x, y
        elif kind == "p2":
            self.x2, self.y2 = x, y

    def params_text(self):
        return f"{self.x1},{self.y1},{self.x2},{self.y2}"

    def set_params_text(self, txt):
        x1, y1, x2, y2 = map(int, parts(txt, 4))
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2

    def to_dict(self):
        return {
            "type": "line",
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        }

    def bbox(self):
        x1, x2 = sorted([self.x1, self.x2])
        y1, y2 = sorted([self.y1, self.y2])
        return (x1, y1, x2, y2)
