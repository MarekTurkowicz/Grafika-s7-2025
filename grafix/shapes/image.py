from dataclasses import dataclass
from typing import List, Tuple, Optional
import tkinter as tk
from .base import Shape, OidMixin

Color = Tuple[int, int, int]


@dataclass
class RasterImage(Shape, OidMixin):
    # Pozycja lewego-górnego rogu na scenie
    x: int
    y: int

    # Rozmiar źródłowy (oryginał z pliku)
    src_w: int
    src_h: int
    src_pixels: List[Color]  # długość = src_w * src_h, skanline'ami od góry

    # Rozmiar wyświetlany (może być różny po skalowaniu)
    w: Optional[int] = None
    h: Optional[int] = None

    # Metadane
    src: Optional[str] = None  # ścieżka do pliku (do serializacji)
    oid: str = ""
    cid: Optional[int] = None  # canvas item id
    _photo: Optional[tk.PhotoImage] = None

    def __post_init__(self):
        if not self.oid:
            self.oid = self._new_oid()
        # domyślnie pokaż 1:1
        if self.w is None:
            self.w = self.src_w
        if self.h is None:
            self.h = self.src_h

    # ---------- narzędzia ----------
    def _clamp_dims(self):
        # minimalnie 1×1
        self.w = max(1, int(self.w))
        self.h = max(1, int(self.h))
        # normalizacja pozycji/rozmiaru na wszelki wypadek
        self.x = int(self.x)
        self.y = int(self.y)

    def _photo_from_pixels(self, w: int, h: int, pixels: List[Color]) -> tk.PhotoImage:
        """Buduje PhotoImage z listy pikseli (w,h) → put() wierszami."""
        img = tk.PhotoImage(width=w, height=h)
        # budujemy wiersz po wierszu
        base = 0
        for y in range(h):
            row_hex = (
                "{"
                + " ".join(
                    f"#{r:02x}{g:02x}{b:02x}" for (r, g, b) in pixels[base : base + w]
                )
                + "}"
            )
            img.put(row_hex, to=(0, y))
            base += w
        return img

    def _scale_nearest(self, dst_w: int, dst_h: int) -> List[Color]:
        """Skalowanie nearest-neighbor z src_pixels (src_w×src_h) → dst_w×dst_h."""
        sw, sh = self.src_w, self.src_h
        spx = self.src_pixels
        out: List[Color] = [(0, 0, 0)] * (dst_w * dst_h)

        # mapowanie: dst (dx,dy) -> src (sx,sy)
        # używamy wersji „floor”, która nie wychodzi poza zakres
        for dy in range(dst_h):
            sy = (dy * sh) // dst_h
            row_base = dy * dst_w
            sy_base = sy * sw
            for dx in range(dst_w):
                sx = (dx * sw) // dst_w
                out[row_base + dx] = spx[sy_base + sx]
        return out

    def _rebuild_photo(self):
        """Przeskaluj i odśwież PhotoImage zgodnie z (w,h)."""
        self._clamp_dims()
        if self.w == self.src_w and self.h == self.src_h:
            # 1:1 — bezpośrednio z oryginału
            self._photo = self._photo_from_pixels(
                self.src_w, self.src_h, self.src_pixels
            )
        else:
            # skalowanie nearest-neighbor
            dst = self._scale_nearest(self.w, self.h)
            self._photo = self._photo_from_pixels(self.w, self.h, dst)

    # ---------- Shape API ----------
    def draw(self, surface, canvas: tk.Canvas):
        self._rebuild_photo()
        self.cid = canvas.create_image(
            self.x,
            self.y,
            image=self._photo,
            anchor="nw",
            tags=("shape", self.oid, "image"),
        )

    def update_canvas(self, surface, canvas: tk.Canvas):
        if not self.cid:
            # jeśli przypadkiem nie narysowane — narysuj
            self.draw(surface, canvas)
            return
        # Zmieniał się rozmiar? trzeba odbudować photo i podmienić obraz
        self._rebuild_photo()
        canvas.itemconfigure(self.cid, image=self._photo)
        canvas.coords(self.cid, self.x, self.y)

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

    def handles(self):
        # 4 rogi do skalowania
        x1, y1, x2, y2 = self.bbox()
        return [
            (x1, y1, "tl"),
            (x2, y1, "tr"),
            (x2, y2, "br"),
            (x1, y2, "bl"),
        ]

    def apply_handle(self, kind, mx, my):
        # Skalowanie swobodne (nie zachowuje proporcji — można dodać Shift później)
        x1, y1, x2, y2 = self.bbox()
        if kind == "tl":
            # górny-lewy: punkt przeciwległy to (x2,y2)
            self.x = mx
            self.y = my
            self.w = x2 - self.x
            self.h = y2 - self.y
        elif kind == "tr":
            self.y = my
            self.w = mx - self.x
            self.h = y2 - self.y
        elif kind == "br":
            self.w = mx - self.x
            self.h = my - self.y
        elif kind == "bl":
            self.x = mx
            self.w = x2 - self.x
            self.h = my - self.y
        # normalizacja (zawsze dodatni rozmiar, x,y to lewy-górny)
        if self.w < 0:
            self.x += self.w
            self.w = -self.w
        if self.h < 0:
            self.y += self.h
            self.h = -self.h
        self._clamp_dims()

    def params_text(self):
        # edytujemy położenie i rozmiar wyświetlany
        return f"{self.x},{self.y},{self.w},{self.h}"

    def set_params_text(self, txt):
        from ..utils import parts

        x, y, w, h = map(int, parts(txt, 4))
        self.x, self.y = x, y
        self.w, self.h = w, h
        self._clamp_dims()

    def to_dict(self):
        # serializujemy ścieżkę (jeśli jest), pozycję i aktualny rozmiar wyświetlany
        d = {"type": "image", "x": self.x, "y": self.y, "w": self.w, "h": self.h}
        if self.src:
            d["src"] = self.src
        # nie zapisujemy src_w/src_h/src_pixels — odczytamy z pliku przy wczytywaniu
        return d

    def bbox(self):
        return (self.x, self.y, self.x + (self.w or 0), self.y + (self.h or 0))
