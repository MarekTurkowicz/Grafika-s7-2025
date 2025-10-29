from .surface import Surface
from .surface_canvas import CanvasSurface

# PhotoImage wariant jest opcjonalny:
from .surface_photoimage import PhotoSurface  # nieużywany domyślnie

__all__ = ["Surface", "CanvasSurface", "PhotoSurface"]
