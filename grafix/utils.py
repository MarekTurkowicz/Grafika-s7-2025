def parts(txt: str, n: int):
    ps = [p.strip() for p in txt.replace(";", ",").split(",") if p.strip()]
    if len(ps) != n:
        raise ValueError(f"Podaj {n} liczb")
    return ps
