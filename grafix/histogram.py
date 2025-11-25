import math


def _luma(r, g, b):
    """Luminancja (0..255) – używana do histogramu."""
    y = 0.299 * r + 0.587 * g + 0.114 * b
    if y < 0:
        y = 0
    elif y > 255:
        y = 255
    return int(round(y))


def compute_histogram(pixels):
    """
    Zwraca histogram (lista 256 elementów) zliczający wystąpienia jasności (luminancja).
    pixels: lista (R,G,B).
    """
    hist = [0] * 256
    for r, g, b in pixels:
        y = _luma(r, g, b)
        hist[y] += 1
    return hist


def histogram_stretch(pixels):
    """
    Rozszerzenie histogramu – przeskalowanie luminancji tak, aby min → 0, max → 255.
    Wynik jest w skali szarości (R=G=B=luminancja).
    """
    hist = compute_histogram(pixels)
    total = sum(hist)
    if total == 0:
        return pixels[:]

    # znajdź min i max intensywność z niezerową liczbą pikseli
    imin = 0
    while imin < 256 and hist[imin] == 0:
        imin += 1
    imax = 255
    while imax >= 0 and hist[imax] == 0:
        imax -= 1

    if imin >= imax:
        # obraz jest prawie jednorodny; po prostu zwróć szary obraz o tej jasności
        gray = imin
        return [(gray, gray, gray) for _ in pixels]

    # przygotuj mapę 0..255 -> 0..255
    mapping = [0] * 256
    scale = 255.0 / (imax - imin)
    for i in range(256):
        if i <= imin:
            v = 0
        elif i >= imax:
            v = 255
        else:
            v = int(round((i - imin) * scale))
        if v < 0:
            v = 0
        elif v > 255:
            v = 255
        mapping[i] = v

    out = []
    for r, g, b in pixels:
        y = _luma(r, g, b)
        v = mapping[y]
        out.append((v, v, v))
    return out


def histogram_equalize(pixels):
    """
    Wyrównanie histogramu (histogram equalization) na luminancji.
    Wynik jest w skali szarości (R=G=B=luminancja).
    """
    hist = compute_histogram(pixels)
    total = sum(hist)
    if total == 0:
        return pixels[:]

    # CDF (dystrybuanta)
    cdf = [0] * 256
    cumsum = 0
    for i in range(256):
        cumsum += hist[i]
        cdf[i] = cumsum

    # najmniejsza wartość CDF > 0
    cdf_min = next((c for c in cdf if c > 0), 0)
    if cdf_min == 0 or cdf[-1] == cdf_min:
        # obraz o bardzo wąskim histogramie → zwróć jak jest (w szarościach)
        out = []
        for r, g, b in pixels:
            y = _luma(r, g, b)
            out.append((y, y, y))
        return out

    denom = total - cdf_min
    mapping = [0] * 256
    for i in range(256):
        v = (cdf[i] - cdf_min) / denom
        if v < 0:
            v = 0.0
        elif v > 1:
            v = 1.0
        val = int(round(v * 255))
        if val < 0:
            val = 0
        elif val > 255:
            val = 255
        mapping[i] = val

    out = []
    for r, g, b in pixels:
        y = _luma(r, g, b)
        v = mapping[y]
        out.append((v, v, v))
    return out
