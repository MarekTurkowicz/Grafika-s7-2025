import tkinter as tk
from typing import Tuple
from .surface import Surface


class PhotoSurface(Surface):
    """
    Eksperymentalny raster PhotoImage (wydajniejszy), ale bez tagów per piksel.
    Uwaga: selekcja po tagach Canvas nie zadziała z tym backendem – używaj CanvasSurface.
    """

    def __init__(self, canvas: tk.Canvas, width: int, height: int):
        self.canvas = canvas
        self.img = tk.PhotoImage(width=width, height=height)
        self.item = canvas.create_image(0, 0, image=self.img, anchor="nw")
        self._batch = []

    def plot(self, x: int, y: int, color: str, tags: Tuple[str, ...]):
        self._batch.append((x, y, color))

    def clear_tag(self, tag: str):
        # Brak tagów – czyścimy całość (niezalecane do selekcji)
        self.img.blank()

    def flush(self):
        for x, y, col in self._batch:
            self.img.put(col, (x, y))
        self._batch.clear()
