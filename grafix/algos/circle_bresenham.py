from typing import List, Tuple


def bresenham_circle(cx: int, cy: int, r: int) -> List[Tuple[int, int]]:
    if r <= 0:
        return []
    pts = []
    x, y = 0, r
    d = 3 - 2 * r

    def add8(cx, cy, x, y):
        pts.extend(
            [
                (cx + x, cy + y),
                (cx - x, cy + y),
                (cx + x, cy - y),
                (cx - x, cy - y),
                (cx + y, cy + x),
                (cx - y, cy + x),
                (cx + y, cy - x),
                (cx - y, cy - x),
            ]
        )

    while x <= y:
        add8(cx, cy, x, y)
        if d < 0:
            d += 4 * x + 6
        else:
            d += 4 * (x - y) + 10
            y -= 1
        x += 1

    # deduplikacja dla małych r
    return list(dict.fromkeys(pts))
