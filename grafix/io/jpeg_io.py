# grafix/io/jpeg_io.py
from typing import List, Tuple

try:
    from PIL import Image
except ImportError as e:
    raise ImportError("Brak biblioteki Pillow. Zainstaluj: pip install Pillow") from e

Color = Tuple[int, int, int]


def read_jpeg(path: str) -> Tuple[int, int, List[Color]]:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    data = list(img.getdata())  # [(r,g,b)...] wierszami od góry
    return w, h, data


def write_jpeg(path: str, w: int, h: int, pixels: List[Color], quality: int = 90):
    img = Image.new("RGB", (w, h))
    img.putdata(pixels)
    # subsampling=0 → najlepsza jakość, optimize=True → mniejsze pliki
    img.save(path, format="JPEG", quality=int(quality), optimize=True, subsampling=0)
