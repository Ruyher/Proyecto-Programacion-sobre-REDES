"""Protocolo de mensajes: JSON, una línea por mensaje (terminada en '\\n').

Todo mensaje es un diccionario con un campo obligatorio ``tipo``.
Los tipos evitan el problema de mezclar eventos puntuales (inicio, desconexión)
con el estado continuo: cada uno se procesa por separado y ninguno se pisa.

Cliente -> Servidor:
    {"tipo": "saltar"}
    {"tipo": "reiniciar"}          # pide otra partida (cuando terminó)

Servidor -> Cliente:
    {"tipo": "asignacion", "jugador": 1|2}
    {"tipo": "sala_llena"}
    {"tipo": "inicio"}             # empieza una partida (con cuenta regresiva)
    {"tipo": "estado", ...}        # snapshot, ver servidor/juego.py
    {"tipo": "desconexion", "jugador": n}
"""
import json

# Cliente -> Servidor
SALTAR = "saltar"
REINICIAR = "reiniciar"

# Servidor -> Cliente
ASIGNACION = "asignacion"
SALA_LLENA = "sala_llena"
INICIO = "inicio"
ESTADO = "estado"
DESCONEXION = "desconexion"

MAX_LINEA = 64 * 1024  # un mensaje legítimo es mucho más chico que esto


def codificar(mensaje: dict) -> bytes:
    """Serializa un mensaje a bytes listos para enviar por el socket."""
    return json.dumps(mensaje, separators=(",", ":")).encode("utf-8") + b"\n"


class Decodificador:
    """Reensambla mensajes a partir del flujo de bytes de TCP.

    TCP es un flujo, no respeta límites de mensaje: una lectura puede traer
    medio mensaje, uno, o varios pegados. Acumulamos en un buffer y devolvemos
    solo las líneas completas.
    """

    def __init__(self):
        self._buf = bytearray()

    def alimentar(self, datos: bytes) -> list:
        """Agrega bytes y devuelve la lista de mensajes completos y válidos.

        Las líneas que no son JSON, o que no son un objeto con ``tipo``, se
        descartan sin cortar la conexión. Si el buffer crece demasiado sin
        ningún salto de línea, el emisor está mal: se lanza ValueError.
        """
        self._buf.extend(datos)
        mensajes = []
        while True:
            fin = self._buf.find(b"\n")
            if fin < 0:
                break
            linea = bytes(self._buf[:fin])
            del self._buf[: fin + 1]
            if not linea.strip():
                continue
            try:
                msg = json.loads(linea.decode("utf-8"))
            except ValueError:  # incluye UnicodeDecodeError y JSONDecodeError
                continue
            if isinstance(msg, dict) and isinstance(msg.get("tipo"), str):
                mensajes.append(msg)
        if len(self._buf) > MAX_LINEA:
            raise ValueError("mensaje demasiado largo sin terminador")
        return mensajes
