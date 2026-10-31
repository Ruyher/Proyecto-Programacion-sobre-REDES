import unittest

from comun import config as C
from servidor.juego import CUENTA, FIN, JUGANDO, Juego


def avanzar(juego, ticks):
    for _ in range(ticks):
        juego.paso()


class TestJuego(unittest.TestCase):
    def test_cuenta_regresiva_y_entrada_ignorada(self):
        j = Juego(1)
        self.assertEqual(j.fase, CUENTA)
        j.entrada(1)  # durante la cuenta no hace nada
        self.assertEqual(j.jugadores[1].vy, 0)
        avanzar(j, C.CUENTA_TICKS)
        self.assertEqual(j.fase, JUGANDO)

    def test_salto_cambia_velocidad(self):
        j = Juego(1)
        avanzar(j, C.CUENTA_TICKS)
        j.entrada(1)
        self.assertEqual(j.jugadores[1].vy, C.SALTO)

    def test_misma_semilla_mismos_termos(self):
        a, b = Juego(42), Juego(42)
        for _ in range(C.CUENTA_TICKS + 300):
            a.paso()
            b.paso()
        self.assertEqual(a.snapshot()["termos"], b.snapshot()["termos"])

    def test_si_nadie_salta_mueren_y_termina(self):
        j = Juego(3)
        avanzar(j, C.CUENTA_TICKS + 600)
        self.assertEqual(j.fase, FIN)
        self.assertFalse(any(h.vivo for h in j.jugadores.values()))

    def test_puntaje_al_pasar_un_termo(self):
        j = Juego(5)
        avanzar(j, C.CUENTA_TICKS)
        # Termo justo por pasar a los jugadores, con el hueco alineado a ellos.
        t = j.termos[0]
        t.sup = 150  # hueco entre y=150 y y=330: ambos horneros caben
        t.x = min(h.x for h in j.jugadores.values()) - C.TERMO_ANCHO + C.TERMO_VEL - 1  # un píxel más allá del umbral
        j.jugadores[1].y, j.jugadores[2].y = 200.0, 200.0
        for h in j.jugadores.values():
            h.vy = -C.GRAVEDAD  # tras el paso de gravedad queda quieto en y
        j.paso()
        self.assertTrue(t.pasado)
        self.assertEqual(j.jugadores[1].puntaje, 1)
        self.assertEqual(j.jugadores[2].puntaje, 1)

    def test_el_muerto_no_suma(self):
        j = Juego(5)
        avanzar(j, C.CUENTA_TICKS)
        j.jugadores[2].vivo = False
        t = j.termos[0]
        t.x = min(h.x for h in j.jugadores.values()) - C.TERMO_ANCHO + C.TERMO_VEL - 1  # un píxel más allá del umbral
        t.sup = 150
        j.jugadores[1].y = 200.0
        j.jugadores[1].vy = -C.GRAVEDAD
        j.paso()
        self.assertEqual(j.jugadores[1].puntaje, 1)
        self.assertEqual(j.jugadores[2].puntaje, 0)

    def test_ganador_y_empate(self):
        j = Juego(1)
        j.jugadores[1].puntaje, j.jugadores[2].puntaje = 3, 1
        self.assertEqual(j.ganador(), 1)
        j.jugadores[2].puntaje = 3
        self.assertEqual(j.ganador(), 0)

    def test_reiniciar_deja_estado_limpio(self):
        j = Juego(1)
        avanzar(j, C.CUENTA_TICKS + 600)
        j.reiniciar(2)
        self.assertEqual(j.fase, CUENTA)
        self.assertTrue(all(h.vivo and h.puntaje == 0 for h in j.jugadores.values()))


if __name__ == "__main__":
    unittest.main()
