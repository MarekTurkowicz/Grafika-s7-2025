import tkinter as tk
from typing import Tuple
from ..constants import PIXEL_SIZE
from .surface import Surface


class CanvasSurface(Surface):
    """Rysowanie pikseli jako prostokąty 1×1 na Canvas, z tagami (do selekcji/clear)."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas

    def plot(self, x: int, y: int, color: str, tags: Tuple[str, ...]):
        self.canvas.create_rectangle(
            x, y, x + PIXEL_SIZE, y + PIXEL_SIZE, outline=color, fill=color, tags=tags
        )

    def clear_tag(self, tag: str):
        try:
            self.canvas.delete(tag)
        except Exception:
            pass

    def flush(self):
        # Canvas tworzy elementy natychmiast; nic do opróżnienia
        pass
