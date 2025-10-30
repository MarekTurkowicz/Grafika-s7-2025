# grafix/io/ppm.py
from typing import List, Tuple, Iterator


def _scale_to_255(v: int, maxval: int) -> int:
    if maxval == 255:
        return v
    return int(round((v / maxval) * 255))


# ---------- P3 (ASCII) – tokenizacja blokowa ----------


def _p3_token_stream(path: str, chunk_size: int = 1 << 20) -> Iterator[str]:
    # Czytamy binarnie, dzielimy na tokeny ASCII, wycinamy komentarze.
    # Strumień zwraca kolejne "słowa" (liczby / magic).
    with open(path, "rb") as f:
        buf = b""
        in_comment = False
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            data = buf + chunk
            i, n = 0, len(data)
            start = None
            tokens = []
            while i < n:
                b = data[i]
                if in_comment:
                    if b in (10, 13):  # koniec linii
                        in_comment = False
                    i += 1
                    continue
                if b == 35:  # '#'
                    in_comment = True
                    i += 1
                    continue
                if chr(b).isspace():
                    if start is not None:
                        tokens.append(data[start:i])
                        start = None
                    i += 1
                    continue
                # zwykły znak (część tokenu)
                if start is None:
                    start = i
                i += 1
            # i==n
            if start is not None:
                # zostaw ogonek do następnego chunka
                buf = data[start:n]
            else:
                buf = b""
            for t in tokens:
                yield t.decode("ascii", errors="strict")
        if buf:
            yield buf.decode("ascii", errors="strict")


def read_ppm_p3(path: str) -> Tuple[int, int, List[Tuple[int, int, int]]]:
    ts = _p3_token_stream(path)
    try:
        magic = next(ts)
    except StopIteration:
        raise ValueError("Pusty plik PPM.")
    if magic != "P3":
        raise ValueError("To nie jest PPM P3 (magic != P3).")
    try:
        w = int(next(ts))
        h = int(next(ts))
        maxval = int(next(ts))
    except StopIteration:
        raise ValueError("Niepełny nagłówek P3.")
    if w <= 0 or h <= 0 or maxval <= 0:
        raise ValueError("Nieprawidłowy nagłówek P3.")
    expected = w * h * 3
    vals: List[int] = []
    for t in ts:
        if len(vals) >= expected:
            break
        vals.append(int(t))
    if len(vals) < expected:
        raise ValueError(f"Za mało próbek RGB: {len(vals)} < {expected}")
    px: List[Tuple[int, int, int]] = []
    it = iter(vals[:expected])
    for _ in range(w * h):
        r = _scale_to_255(next(it), maxval)
        g = _scale_to_255(next(it), maxval)
        b = _scale_to_255(next(it), maxval)
        px.append((r, g, b))
    return w, h, px


# ---------- P6 (binarny) ----------


def read_ppm_p6(path: str) -> Tuple[int, int, List[Tuple[int, int, int]]]:
    import io

    with open(path, "rb") as raw:
        f = io.BufferedReader(raw)

        def next_token():
            ch = f.read(1)
            while ch:
                if ch == b"#":
                    # komentarz do końca linii
                    while True:
                        c2 = f.read(1)
                        if not c2 or c2 in (b"\n", b"\r"):
                            break
                elif ch.isspace():
                    pass
                else:
                    break
                ch = f.read(1)
            if not ch:
                return None
            tok = bytearray()
            tok.extend(ch)
            while True:
                c = f.peek(1)[:1]
                if not c or c.isspace() or c == b"#":
                    break
                f.read(1)
                tok.extend(c)
            return bytes(tok)

        magic = next_token()
        if magic != b"P6":
            raise ValueError("To nie jest PPM P6 (magic != P6).")
        w = int(next_token())
        h = int(next_token())
        maxval = int(next_token())
        if w <= 0 or h <= 0 or maxval <= 0:
            raise ValueError("Nieprawidłowy nagłówek P6.")

        sep = f.read(1)
        if not sep or not sep.isspace():
            raise ValueError("Brak separatora danych po nagłówku P6.")

        bps = 1 if maxval <= 255 else 2
        total = w * h * 3 * bps
        buf = f.read(total)
        if len(buf) < total:
            raise ValueError("Za mało danych binarnych w P6.")
        px: List[Tuple[int, int, int]] = []
        if bps == 1:
            it = iter(buf)
            for _ in range(w * h):
                r = _scale_to_255(next(it), maxval)
                g = _scale_to_255(next(it), maxval)
                b = _scale_to_255(next(it), maxval)
                px.append((r, g, b))
        else:
            for i in range(0, len(buf), 6):
                r16 = (buf[i] << 8) | buf[i + 1]
                g16 = (buf[i + 2] << 8) | buf[i + 3]
                b16 = (buf[i + 4] << 8) | buf[i + 5]
                px.append(
                    (
                        _scale_to_255(r16, maxval),
                        _scale_to_255(g16, maxval),
                        _scale_to_255(b16, maxval),
                    )
                )
        return w, h, px


# ---------- autodetekcja ----------


def read_ppm_auto(path: str):
    with open(path, "rb") as f:
        magic = f.read(2)
    if magic == b"P3":
        w, h, px = read_ppm_p3(path)
        return w, h, px, "P3"
    if magic == b"P6":
        w, h, px = read_ppm_p6(path)
        return w, h, px, "P6"
    raise ValueError("Nieznany format PPM (magic nie P3/P6).")
