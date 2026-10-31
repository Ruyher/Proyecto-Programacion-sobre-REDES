"""Servidor autoritativo de Flappy Hornero Online.

Los clientes solo mandan *entradas* (saltar). El servidor corre la física a
tick fijo y difunde snapshots del estado. Así nadie puede hacer trampa
mandando posiciones, y ningún jugador depende de la conexión del otro para
que el juego avance.

Uso:  python -m servidor.main [--host 0.0.0.0] [--puerto 5050]
"""
import argparse
import logging
import queue
import random
import socket
import threading
import time

from comun import config as C
from comun import protocolo as P
from servidor.juego import FIN, Juego

log = logging.getLogger("servidor")


class Conexion:
    """Un cliente conectado, con su propia cola y hilo de escritura.

    Escribir desde un hilo aparte evita que un cliente lento bloquee el bucle
    del juego (sendall puede quedarse esperando).
    """

    def __init__(self, sock: socket.socket, addr, id_jugador: int):
        self.sock = sock
        self.addr = addr
        self.id = id_jugador
        self.viva = True
        self._salida = queue.Queue(maxsize=128)

    def enviar(self, mensaje: dict) -> bool:
        if not self.viva:
            return False
        try:
            self._salida.put_nowait(P.codificar(mensaje))
            return True
        except queue.Full:  # cliente que no consume: lo cortamos
            log.warning("jugador %s: cola llena, se cierra la conexión", self.id)
            self.cerrar()
            return False

    def bucle_escritura(self):
        while True:
            datos = self._salida.get()
            if datos is None:
                break
            try:
                self.sock.sendall(datos)
            except OSError:
                break
        self.cerrar()

    def cerrar(self):
        if not self.viva:
            return
        self.viva = False
        for accion in (lambda: self.sock.shutdown(socket.SHUT_RDWR), self.sock.close):
            try:
                accion()
            except OSError:
                pass
        try:
            self._salida.put_nowait(None)  # despierta al hilo de escritura
        except queue.Full:
            pass


class Servidor:
    def __init__(self, host: str = C.HOST_SERVIDOR, puerto: int = C.PUERTO, semilla=None):
        self._lock = threading.Lock()   # protege conexiones, juego y en_partida
        self._conexiones = {}           # id_jugador -> Conexion
        self._listos = set()            # quienes pidieron revancha
        self._en_partida = False
        self._semilla = semilla
        self.juego = Juego(semilla)
        self._detener = threading.Event()

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, puerto))
        self._sock.listen(8)
        self.puerto = self._sock.getsockname()[1]  # útil si se pidió puerto 0

    # ------------------------------------------------------------ ciclo de vida
    def arrancar(self):
        """Lanza los hilos de aceptación y de juego (no bloquea)."""
        threading.Thread(target=self._bucle_aceptar, daemon=True).start()
        threading.Thread(target=self._bucle_juego, daemon=True).start()
        log.info("escuchando en el puerto %s", self.puerto)

    def servir_siempre(self):
        self.arrancar()
        try:
            while not self._detener.wait(0.5):
                pass
        except KeyboardInterrupt:
            log.info("cerrando servidor")
        finally:
            self.detener()

    def detener(self):
        self._detener.set()
        try:
            self._sock.close()
        except OSError:
            pass
        with self._lock:
            for c in list(self._conexiones.values()):
                c.cerrar()

    # ------------------------------------------------------------ conexiones
    def _bucle_aceptar(self):
        while not self._detener.is_set():
            try:
                sock, addr = self._sock.accept()
            except OSError:
                break
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # sin demora de Nagle
            threading.Thread(target=self._atender, args=(sock, addr), daemon=True).start()

    def _atender(self, sock: socket.socket, addr):
        with self._lock:
            libre = next(
                (i for i in range(1, C.MAX_JUGADORES + 1) if i not in self._conexiones),
                None,
            )
            conn = None
            if libre is not None:
                conn = Conexion(sock, addr, libre)
                self._conexiones[libre] = conn
                conn.enviar({"tipo": P.ASIGNACION, "jugador": libre})
                log.info("jugador %s conectado desde %s", libre, addr)
                self._intentar_iniciar()

        if conn is None:
            log.info("sala llena, se rechaza a %s", addr)
            try:
                sock.sendall(P.codificar({"tipo": P.SALA_LLENA}))
            except OSError:
                pass
            sock.close()
            return

        threading.Thread(target=conn.bucle_escritura, daemon=True).start()
        decodificador = P.Decodificador()
        try:
            while True:
                datos = sock.recv(4096)
                if not datos:
                    break
                for msg in decodificador.alimentar(datos):
                    self._procesar(conn, msg)
        except (OSError, ValueError) as e:
            log.info("jugador %s: conexión terminada (%s)", conn.id, e)
        finally:
            self._quitar(conn)

    def _quitar(self, conn: Conexion):
        with self._lock:
            if self._conexiones.get(conn.id) is conn:
                del self._conexiones[conn.id]
                self._listos.discard(conn.id)
                log.info("jugador %s desconectado", conn.id)
                if self._en_partida:
                    self._en_partida = False
                    self._difundir({"tipo": P.DESCONEXION, "jugador": conn.id})
        conn.cerrar()

    # ------------------------------------------------------------ mensajes
    def _procesar(self, conn: Conexion, msg: dict):
        tipo = msg["tipo"]
        with self._lock:
            if tipo == P.SALTAR and self._en_partida:
                self.juego.entrada(conn.id)
            elif tipo == P.REINICIAR and self._en_partida and self.juego.fase == FIN:
                self._listos.add(conn.id)
                if len(self._listos) == C.MAX_JUGADORES:
                    self._iniciar_partida()
            # tipos desconocidos: se ignoran

    def _intentar_iniciar(self):
        """Debe llamarse con el lock tomado."""
        if len(self._conexiones) == C.MAX_JUGADORES and not self._en_partida:
            self._iniciar_partida()

    def _iniciar_partida(self):
        """Debe llamarse con el lock tomado."""
        semilla = self._semilla if self._semilla is not None else random.random()
        self.juego.reiniciar(semilla)
        self._listos.clear()
        self._en_partida = True
        self._difundir({"tipo": P.INICIO})

    def _difundir(self, mensaje: dict):
        """Debe llamarse con el lock tomado."""
        for c in list(self._conexiones.values()):
            c.enviar(mensaje)

    # ------------------------------------------------------------ bucle de juego
    def _bucle_juego(self):
        dt = 1.0 / C.TICK_HZ
        proximo = time.monotonic()
        while not self._detener.is_set():
            proximo += dt
            with self._lock:
                if self._en_partida:
                    fase_antes = self.juego.fase
                    self.juego.paso()
                    cambio = self.juego.fase != fase_antes
                    periodico = self.juego.fase != FIN and self.juego.tick % C.SNAPSHOT_DIV == 0
                    if cambio or periodico:
                        self._difundir(self.juego.snapshot())
            espera = proximo - time.monotonic()
            if espera > 0:
                time.sleep(espera)
            else:
                proximo = time.monotonic()  # nos atrasamos: no acumular deuda


def main():
    ap = argparse.ArgumentParser(description="Servidor de Flappy Hornero Online")
    ap.add_argument("--host", default=C.HOST_SERVIDOR)
    ap.add_argument("--puerto", type=int, default=C.PUERTO)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    Servidor(args.host, args.puerto).servir_siempre()


if __name__ == "__main__":
    main()
