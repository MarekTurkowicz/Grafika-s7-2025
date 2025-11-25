import math


def _luma(r, g, b):
    y = 0.299 * r + 0.587 * g + 0.114 * b
    if y < 0:
        y = 0
    elif y > 255:
        y = 255
    return int(round(y))


def _to_gray_list(pixels):
    """Zwraca listę jasności 0..255 dla wszystkich pikseli."""
    return [_luma(r, g, b) for (r, g, b) in pixels]


def _apply_threshold_to_pixels(pixels, T):
    """
    Zastosowanie progu T (0..255) do całego obrazu:
    y < T → czarny, y >= T → biały. Zwraca (R,G,B) z 0/255.
    """
    out = []
    for r, g, b in pixels:
        y = _luma(r, g, b)
        v = 0 if y < T else 255
        out.append((v, v, v))
    return out


def threshold_manual(pixels, T):
    """Ręczna binaryzacja – użytkownik podaje próg T."""
    if T < 0:
        T = 0
    elif T > 255:
        T = 255
    return _apply_threshold_to_pixels(pixels, T)


def threshold_percent_black(pixels, percent_black):
    """
    Percent Black Selection – wybieramy próg taki, by ~percent_black% pikseli było czarnych.
    percent_black w [0,100].
    """
    if percent_black < 0:
        percent_black = 0.0
    elif percent_black > 100:
        percent_black = 100.0

    vals = _to_gray_list(pixels)
    n = len(vals)
    if n == 0:
        return pixels[:]

    # histogram + kumulacja
    hist = [0] * 256
    for v in vals:
        hist[v] += 1

    target = n * (percent_black / 100.0)
    cumsum = 0
    T = 0
    for i in range(256):
        cumsum += hist[i]
        if cumsum >= target:
            T = i
            break

    return _apply_threshold_to_pixels(pixels, T)


def threshold_mean_iterative(pixels, max_iter=100, eps=0.5):
    """
    Mean Iterative Selection – iteracyjny próg średniej.
    """
    vals = _to_gray_list(pixels)
    n = len(vals)
    if n == 0:
        return pixels[:]

    # początkowy próg – globalna średnia
    T = sum(vals) / n

    for _ in range(max_iter):
        g1 = [v for v in vals if v <= T]
        g2 = [v for v in vals if v > T]
        if not g1 or not g2:
            break
        m1 = sum(g1) / len(g1)
        m2 = sum(g2) / len(g2)
        new_T = (m1 + m2) / 2.0
        if abs(new_T - T) < eps:
            T = new_T
            break
        T = new_T

    T_int = int(round(T))
    return _apply_threshold_to_pixels(pixels, T_int)


def threshold_entropy(pixels):
    """
    Selekcja entropii (Kapur) – maksymalizacja sumy entropii tła i obiektu.
    """
    vals = _to_gray_list(pixels)
    n = len(vals)
    if n == 0:
        return pixels[:]

    hist = [0] * 256
    for v in vals:
        hist[v] += 1

    total = float(n)
    p = [h / total for h in hist]

    best_T = 0
    best_H = -1e9

    for T in range(0, 255):
        # tło: [0..T], obiekt: [T+1..255]
        p1 = sum(p[0 : T + 1])
        p2 = sum(p[T + 1 : 256])
        if p1 <= 0.0 or p2 <= 0.0:
            continue

        H1 = 0.0
        for i in range(0, T + 1):
            if p[i] > 0.0:
                pi = p[i] / p1
                H1 -= pi * math.log(pi + 1e-12)

        H2 = 0.0
        for i in range(T + 1, 256):
            if p[i] > 0.0:
                pi = p[i] / p2
                H2 -= pi * math.log(pi + 1e-12)

        H = H1 + H2
        if H > best_H:
            best_H = H
            best_T = T

    return _apply_threshold_to_pixels(pixels, best_T)
