"""Pruebas de punta a punta: servidor real + clientes reales por sockets locales."""
import queue
import time
import unittest

from cliente.red import ClienteRed
from comun import config as C
from comun import protocolo as P
from servidor.main import Servidor


def esperar(cliente, tipo, timeout=5.0):
    """Espera un mensaje de ese tipo y lo devuelve (descarta los demás)."""
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        try:
            msg = cliente.mensajes.get(timeout=0.1)
        except queue.Empty:
            continue
        if msg["tipo"] == tipo:
            return msg
    raise AssertionError(f"no llegó un mensaje '{tipo}' en {timeout}s")


class TestIntegracion(unittest.TestCase):
    def setUp(self):
        self.srv = Servidor("127.0.0.1", 0, semilla=1)
        self.srv.arrancar()
        self.clientes = []

    def tearDown(self):
        for c in self.clientes:
            c.cerrar()
        self.srv.detener()

    def nuevo(self):
        c = ClienteRed()
        c.conectar("127.0.0.1", self.srv.puerto)
        self.clientes.append(c)
        return c

    def test_asignacion_e_inicio(self):
        a, b = self.nuevo(), self.nuevo()
        self.assertEqual(esperar(a, P.ASIGNACION)["jugador"], 1)
        self.assertEqual(esperar(b, P.ASIGNACION)["jugador"], 2)
        esperar(a, P.INICIO)
        esperar(b, P.INICIO)
        snap = esperar(a, P.ESTADO)
        self.assertIn("jugadores", snap)

    def test_tercer_cliente_recibe_sala_llena(self):
        self.nuevo(), self.nuevo()
        c = self.nuevo()
        esperar(c, P.SALA_LLENA)

    def test_desconexion_avisada_y_slot_reutilizado(self):
        """El bug de Pong: si se iba el J1 y entraba otro, quedaban dos 'jugador 2'."""
        a, b = self.nuevo(), self.nuevo()
        esperar(a, P.ASIGNACION)
        esperar(b, P.ASIGNACION)
        esperar(b, P.INICIO)
        a.cerrar()
        self.assertEqual(esperar(b, P.DESCONEXION)["jugador"], 1)
        c = self.nuevo()
        self.assertEqual(esperar(c, P.ASIGNACION)["jugador"], 1)  # ocupa el lugar libre
        esperar(b, P.INICIO)  # y la partida vuelve a empezar

    def test_saltar_modifica_el_estado(self):
        a, b = self.nuevo(), self.nuevo()
        esperar(a, P.INICIO)
        # esperar a que termine la cuenta regresiva
        while esperar(a, P.ESTADO)["fase"] != "JUGANDO":
            pass
        a.enviar({"tipo": P.SALTAR})
        # el J1 sube respecto del J2 (que cae): su y debe quedar por encima
        fin = time.monotonic() + 2
        while time.monotonic() < fin:
            j = esperar(a, P.ESTADO)["jugadores"]
            if j["1"]["y"] < j["2"]["y"] - 100:
                break
        else:
            self.fail("el salto del jugador 1 no se reflejó en el estado")

    def test_basura_no_tumba_la_conexion(self):
        a, b = self.nuevo(), self.nuevo()
        esperar(a, P.INICIO)
        a._sock.sendall(b"esto no es json\n{\"x\":1}\n")
        a.enviar({"tipo": P.SALTAR})
        esperar(a, P.ESTADO)  # sigue recibiendo estados
        self.assertTrue(a.conectado)

    def test_revancha_cuando_ambos_la_piden(self):
        a, b = self.nuevo(), self.nuevo()
        esperar(a, P.INICIO)
        esperar(b, P.INICIO)
        # nadie salta: ambos mueren y la partida termina
        while esperar(a, P.ESTADO, timeout=15)["fase"] != "FIN":
            pass
        a.enviar({"tipo": P.REINICIAR})
        time.sleep(0.3)
        # con un solo voto no reinicia: b no debe haber recibido ningún INICIO
        self.assertFalse(any(m["tipo"] == P.INICIO for m in b.sacar_mensajes()))
        b.enviar({"tipo": P.REINICIAR})
        esperar(a, P.INICIO)
        esperar(b, P.INICIO)


if __name__ == "__main__":
    unittest.main()
