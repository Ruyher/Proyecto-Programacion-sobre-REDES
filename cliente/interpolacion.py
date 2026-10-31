"""Interpolación entre snapshots. Sin Pygame, para poder testearla."""


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def interpolar(prev, curr, alpha: float):
    """Mezcla dos snapshots.

    Devuelve (y_por_jugador, [(x, sup) de cada termo]). Si no hay snapshot
    previo, o un termo/jugador es nuevo, se usa el valor actual sin mezclar.
    """
    ys = {}
    for k, j in curr["jugadores"].items():
        y0 = prev["jugadores"][k]["y"] if prev and k in prev["jugadores"] else j["y"]
        ys[int(k)] = lerp(y0, j["y"], alpha)
    x_prev = {t["id"]: t["x"] for t in prev["termos"]} if prev else {}
    termos = [(lerp(x_prev.get(t["id"], t["x"]), t["x"], alpha), t["sup"]) for t in curr["termos"]]
    return ys, termos
