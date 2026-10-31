"""Conexión del cliente. No depende de Pygame (se puede testear sola).

Un hilo recibe y decodifica; los mensajes llegan al juego por una cola, en
orden y sin pisarse. A diferencia de guardar "el último mensaje", así ningún
evento (inicio, desconexión...) se pierde aunque lleguen varios juntos.
"""
import queue
import socket
import threading

from comun import config as C
from comun import protocolo as P

CERRADA = "_cerrada"  # mensaje interno: se perdió la conexión


class ClienteRed:
    def __init__(self):
        self.mensajes = queue.Queue()
        self.conectado = False
        self._sock = None
        self._lock_envio = threading.Lock()

    def conectar(self, ip: str, puerto: int = C.PUERTO, timeout: float = 5.0):
        """Conecta al servidor. Lanza OSError si falla."""
        sock = socket.create_connection((ip, puerto), timeout=timeout)
        sock.settimeout(None)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = sock
        self.conectado = True
        threading.Thread(target=self._bucle_recepcion, daemon=True).start()

    def _bucle_recepcion(self):
        decodificador = P.Decodificador()
        try:
            while True:
                datos = self._sock.recv(4096)
                if not datos:
                    break
                for msg in decodificador.alimentar(datos):
                    self.mensajes.put(msg)
        except (OSError, ValueError):
            pass
        finally:
            self.conectado = False
            self.mensajes.put({"tipo": CERRADA})

    def enviar(self, mensaje: dict) -> bool:
        if not self.conectado:
            return False
        try:
            with self._lock_envio:
                self._sock.sendall(P.codificar(mensaje))
            return True
        except OSError:
            self.cerrar()
            return False

    def sacar_mensajes(self) -> list:
        """Devuelve todos los mensajes pendientes, sin bloquear."""
        salida = []
        while True:
            try:
                salida.append(self.mensajes.get_nowait())
            except queue.Empty:
                return salida

    def cerrar(self):
        self.conectado = False
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
