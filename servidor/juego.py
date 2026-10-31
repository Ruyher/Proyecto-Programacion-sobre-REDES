"""Lógica del juego. Pura: no sabe nada de sockets ni de Pygame.

Que sea pura permite testearla sin red y ejecutarla de forma determinista
(misma semilla -> mismos termos).
"""
import math
import random

from comun import config as C

CUENTA = "CUENTA"
JUGANDO = "JUGANDO"
FIN = "FIN"


class Hornero:
    def __init__(self, id_jugador: int):
        self.id = id_jugador
        self.x = C.X_JUGADOR[id_jugador]
        self.y = float(C.Y_INICIAL[id_jugador])
        self.vy = 0.0
        self.vivo = True
        self.puntaje = 0

    def actualizar(self):
        if self.vivo:
            self.vy += C.GRAVEDAD
            self.y += self.vy

    def saltar(self):
        if self.vivo:
            self.vy = C.SALTO


class Termo:
    def __init__(self, id_termo: int, x: float, sup: int):
        self.id = id_termo
        self.x = float(x)
        self.sup = sup  # alto del termo de arriba; el de abajo se deduce
        self.pasado = False

    @property
    def inf(self) -> int:
        return C.ALTO - self.sup - C.HUECO


def _solapan(ax, ay, aw, ah, bx, by, bw, bh) -> bool:
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


class Juego:
    def __init__(self, semilla=None):
        self.reiniciar(semilla)

    def reiniciar(self, semilla=None):
        self._rng = random.Random(semilla)
        self.jugadores = {i: Hornero(i) for i in range(1, C.MAX_JUGADORES + 1)}
        self._sig_id = 0
        self.termos = [self._nuevo_termo(C.PRIMER_TERMO_X)]
        self.tick = 0
        self.fase = CUENTA
        self.cuenta = C.CUENTA_TICKS

    def _nuevo_termo(self, x: float) -> Termo:
        self._sig_id += 1
        return Termo(self._sig_id, x, self._rng.randint(C.SUP_MIN, C.SUP_MAX))

    # ------------------------------------------------------------------
    def entrada(self, id_jugador: int):
        """Un jugador pidió saltar. Se ignora fuera de la fase JUGANDO."""
        if self.fase == JUGANDO and id_jugador in self.jugadores:
            self.jugadores[id_jugador].saltar()

    def paso(self):
        """Avanza la simulación un tick."""
        if self.fase == FIN:
            return
        self.tick += 1

        if self.fase == CUENTA:
            self.cuenta -= 1
            if self.cuenta <= 0:
                self.fase = JUGANDO
            return

        for h in self.jugadores.values():
            h.actualizar()
            if h.vivo and (h.y + C.HORNERO_ALTO >= C.ALTO - C.SUELO or h.y <= 0):
                h.vivo = False

        if self.termos[-1].x < C.ANCHO - C.DIST_SPAWN:
            self.termos.append(self._nuevo_termo(C.ANCHO))

        x_min = min(h.x for h in self.jugadores.values())
        for t in self.termos:
            t.x -= C.TERMO_VEL
            for h in self.jugadores.values():
                if h.vivo and self._choca(h, t):
                    h.vivo = False
            if not t.pasado and t.x + C.TERMO_ANCHO < x_min:
                t.pasado = True
                for h in self.jugadores.values():
                    if h.vivo:
                        h.puntaje += 1

        self.termos = [t for t in self.termos if t.x + C.TERMO_ANCHO > 0]

        if not any(h.vivo for h in self.jugadores.values()):
            self.fase = FIN

    @staticmethod
    def _choca(h: Hornero, t: Termo) -> bool:
        arriba = _solapan(h.x, h.y, C.HORNERO_ANCHO, C.HORNERO_ALTO,
                          t.x, 0, C.TERMO_ANCHO, t.sup)
        abajo = _solapan(h.x, h.y, C.HORNERO_ANCHO, C.HORNERO_ALTO,
                         t.x, C.ALTO - t.inf, C.TERMO_ANCHO, t.inf)
        return arriba or abajo

    def ganador(self) -> int:
        """Id del ganador, o 0 si hay empate. Solo tiene sentido en FIN."""
        p = {i: h.puntaje for i, h in self.jugadores.items()}
        mejor = max(p.values())
        mejores = [i for i, v in p.items() if v == mejor]
        return mejores[0] if len(mejores) == 1 else 0

    def snapshot(self) -> dict:
        """Estado que se envía a los clientes (ver protocolo.ESTADO)."""
        return {
            "tipo": "estado",
            "tick": self.tick,
            "fase": self.fase,
            "cuenta": math.ceil(self.cuenta / C.TICK_HZ) if self.fase == CUENTA else 0,
            "ganador": self.ganador() if self.fase == FIN else None,
            "jugadores": {
                str(i): {"y": round(h.y, 2), "vivo": h.vivo, "puntaje": h.puntaje}
                for i, h in self.jugadores.items()
            },
            "termos": [
                {"id": t.id, "x": round(t.x, 2), "sup": t.sup} for t in self.termos
            ],
        }
