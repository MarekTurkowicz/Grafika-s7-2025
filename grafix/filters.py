import math


def _clamp_byte(v: float) -> int:
    v = int(round(v))
    if v < 0:
        return 0
    if v > 255:
        return 255
    return v


def _to_2d(pixels, w, h):
    return [pixels[y * w : (y + 1) * w] for y in range(h)]


def _to_1d(rows):
    out = []
    for row in rows:
        out.extend(row)
    return out


def _conv_rgb(pixels, w, h, kernel):
    """Splot maski na każdym kanale RGB osobno."""
    src = _to_2d(pixels, w, h)
    kh = len(kernel)
    kw = len(kernel[0])
    ky = kh // 2
    kx = kw // 2

    out = [[(0, 0, 0) for _ in range(w)] for _ in range(h)]

    for y in range(h):
        for x in range(w):
            acc_r = acc_g = acc_b = 0.0
            for j in range(kh):
                for i in range(kw):
                    yy = y + j - ky
                    xx = x + i - kx
                    if yy < 0:
                        yy = 0
                    if yy >= h:
                        yy = h - 1
                    if xx < 0:
                        xx = 0
                    if xx >= w:
                        xx = w - 1
                    wgt = kernel[j][i]
                    r, g, b = src[yy][xx]
                    acc_r += r * wgt
                    acc_g += g * wgt
                    acc_b += b * wgt
            out[y][x] = (
                _clamp_byte(acc_r),
                _clamp_byte(acc_g),
                _clamp_byte(acc_b),
            )
    return _to_1d(out)


# 1) Filtr wygładzający (uśredniający)


def filter_box_blur(pixels, w, h, size=3):
    if size % 2 == 0 or size < 1:
        raise ValueError("Rozmiar maski musi być nieparzysty i >= 1.")
    n = size * size
    k = [[1.0 / n for _ in range(size)] for _ in range(size)]
    return _conv_rgb(pixels, w, h, k)


# 2) Filtr medianowy (3x3)


def filter_median(pixels, w, h, size=3):
    if size % 2 == 0 or size < 1:
        raise ValueError("Rozmiar maski musi być nieparzysty i >= 1.")

    src = _to_2d(pixels, w, h)
    r = size // 2
    out = [[(0, 0, 0) for _ in range(w)] for _ in range(h)]

    for y in range(h):
        for x in range(w):
            neigh_r = []
            neigh_g = []
            neigh_b = []
            for j in range(-r, r + 1):
                for i in range(-r, r + 1):
                    yy = y + j
                    xx = x + i
                    if yy < 0:
                        yy = 0
                    if yy >= h:
                        yy = h - 1
                    if xx < 0:
                        xx = 0
                    if xx >= w:
                        xx = w - 1
                    rr, gg, bb = src[yy][xx]
                    neigh_r.append(rr)
                    neigh_g.append(gg)
                    neigh_b.append(bb)
            neigh_r.sort()
            neigh_g.sort()
            neigh_b.sort()
            m_idx = len(neigh_r) // 2
            out[y][x] = (
                neigh_r[m_idx],
                neigh_g[m_idx],
                neigh_b[m_idx],
            )
    return _to_1d(out)


# 3) Sobel – wykrywanie krawędzi (na obrazie w skali szarości)


def _to_gray_avg(pixels):
    g_list = []
    for r, g, b in pixels:
        g_list.append(int(round((r + g + b) / 3.0)))
    return g_list


def filter_sobel(pixels, w, h):
    """Zwraca obraz w skali szarości z krawędziami."""
    gray = _to_gray_avg(pixels)
    src = [gray[y * w : (y + 1) * w] for y in range(h)]

    gx_k = [
        [-1, 0, 1],
        [-2, 0, 2],
        [-1, 0, 1],
    ]
    gy_k = [
        [-1, -2, -1],
        [0, 0, 0],
        [1, 2, 1],
    ]

    out = [[0 for _ in range(w)] for _ in range(h)]

    for y in range(h):
        for x in range(w):
            gx = gy = 0.0
            for j in range(3):
                for i in range(3):
                    yy = y + j - 1
                    xx = x + i - 1
                    if yy < 0:
                        yy = 0
                    if yy >= h:
                        yy = h - 1
                    if xx < 0:
                        xx = 0
                    if xx >= w:
                        xx = w - 1
                    v = src[yy][xx]
                    gx += v * gx_k[j][i]
                    gy += v * gy_k[j][i]
            mag = math.sqrt(gx * gx + gy * gy)
            out[y][x] = _clamp_byte(mag)

    # konwersja na RGB
    flat = []
    for row in out:
        for g in row:
            flat.append((g, g, g))
    return flat


# 4) Filtr górnoprzepustowy wyostrzający (klasyczna maska)


def filter_sharpen(pixels, w, h):
    kernel = [
        [0, -1, 0],
        [-1, 5, -1],
        [0, -1, 0],
    ]
    return _conv_rgb(pixels, w, h, kernel)


# 5) Rozmycie gaussowskie (5x5)


def filter_gaussian(pixels, w, h):
    kernel = [
        [1, 4, 6, 4, 1],
        [4, 16, 24, 16, 4],
        [6, 24, 36, 24, 6],
        [4, 16, 24, 16, 4],
        [1, 4, 6, 4, 1],
    ]
    norm = 1.0 / 256.0
    kernel = [[v * norm for v in row] for row in kernel]
    return _conv_rgb(pixels, w, h, kernel)


# 6) Splot maski dowolnego rozmiaru (dla chętnych)


def filter_custom(pixels, w, h, kernel):
    """Splot dla dowolnej maski (lista list float)."""
    return _conv_rgb(pixels, w, h, kernel)
