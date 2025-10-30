# Własne, odporne parsowanie PPM P3 i P6 (bez PIL itp.)
# Zwracamy: (w, h, pixels) gdzie pixels = [(r,g,b), ...] wierszami od góry.

from typing import List, Tuple

# --- Wspólne ---


def _scale_to_255(v: int, maxval: int) -> int:
    if maxval == 255:
        return v
    # skalowanie x -> [0..255]
    return int(round((v / maxval) * 255))


# --- P3: ASCII, ale parsowane binarnie (odporne na komentarze/znaki 8-bit) ---


def read_ppm_p3(path: str) -> Tuple[int, int, List[Tuple[int, int, int]]]:
    with open(path, "rb") as f:
        data = f.read()

    n = len(data)
    i = 0

    def is_space(b: int) -> bool:
        # białe znaki ASCII
        return chr(b).isspace()

    def skip_ws_and_comments(i: int) -> int:
        while i < n:
            b = data[i]
            if b == 35:  # '#'
                i += 1
                # do końca linii
                while i < n and data[i] not in (10, 13):  # '\n' '\r'
                    i += 1
            elif is_space(b):
                i += 1
            else:
                break
        return i

    def read_token(i: int):
        i = skip_ws_and_comments(i)
        if i >= n:
            return None, i
        start = i
        while i < n:
            b = data[i]
            if b == 35 or is_space(b):
                break
            i += 1
        # token musi być czystym ASCII wg spec; jeśli trafi się inny bajt – to i tak nie jest cyfra
        tok = data[start:i].decode("ascii", errors="strict")
        return tok, i

    # nagłówek
    tok, i = read_token(i)
    if tok != "P3":
        raise ValueError("To nie jest plik PPM P3 (magic != P3).")
    w_s, i = read_token(i)
    h_s, i = read_token(i)
    max_s, i = read_token(i)
    if not (w_s and h_s and max_s):
        raise ValueError("Niepełny nagłówek P3.")
    w, h, maxval = int(w_s), int(h_s), int(max_s)
    if w <= 0 or h <= 0 or maxval <= 0:
        raise ValueError("Nieprawidłowy nagłówek P3.")

    expected = w * h * 3
    vals: List[int] = []
    while len(vals) < expected:
        t, i = read_token(i)
        if t is None:
            break
        vals.append(int(t))
    if len(vals) < expected:
        raise ValueError(f"Za mało próbek RGB: {len(vals)} < {expected}")

    pixels: List[Tuple[int, int, int]] = []
    it = iter(vals[:expected])
    for _ in range(w * h):
        r = _scale_to_255(next(it), maxval)
        g = _scale_to_255(next(it), maxval)
        b = _scale_to_255(next(it), maxval)
        pixels.append((r, g, b))
    return w, h, pixels


# --- P6: binarny, 8/16-bit per kanał ---


def read_ppm_p6(path: str) -> Tuple[int, int, List[Tuple[int, int, int]]]:
    import io

    with open(path, "rb") as raw:
        f = io.BufferedReader(raw)

        def next_token():
            # pomiń białe znaki i komentarze
            ch = f.read(1)
            while ch:
                if ch == b"#":
                    # do końca linii
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
                f.read(1)  # konsumuj
                tok.extend(c)
            return bytes(tok)

        magic = next_token()
        if magic != b"P6":
            raise ValueError("To nie jest plik PPM P6 (magic != P6).")
        w = int(next_token())
        h = int(next_token())
        maxval = int(next_token())
        if w <= 0 or h <= 0 or maxval <= 0:
            raise ValueError("Nieprawidłowy nagłówek P6.")

        # separator (whitespace) przed danymi
        sep = f.read(1)
        if not sep or not sep.isspace():
            raise ValueError("Brak separatora danych binarnych po nagłówku P6.")

        bps = 1 if maxval <= 255 else 2
        total = w * h * 3 * bps
        buf = f.read(total)
        if len(buf) < total:
            raise ValueError(f"Za mało danych binarnych w P6: {len(buf)} < {total}")

        pixels: List[Tuple[int, int, int]] = []
        if bps == 1:
            it = iter(buf)
            for _ in range(w * h):
                r = _scale_to_255(next(it), maxval)
                g = _scale_to_255(next(it), maxval)
                b = _scale_to_255(next(it), maxval)
                pixels.append((r, g, b))
        else:
            # 16-bit big-endian na kanał
            for i in range(0, len(buf), 6):
                r16 = (buf[i] << 8) | buf[i + 1]
                g16 = (buf[i + 2] << 8) | buf[i + 3]
                b16 = (buf[i + 4] << 8) | buf[i + 5]
                pixels.append(
                    (
                        _scale_to_255(r16, maxval),
                        _scale_to_255(g16, maxval),
                        _scale_to_255(b16, maxval),
                    )
                )
        return w, h, pixels


# --- Autodetekcja ---


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
