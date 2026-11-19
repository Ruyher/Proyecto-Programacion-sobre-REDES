

Flappy online para dos jugadores en red. Combina la temática y la mecánica de Flappy con la idea cliente-servidor.

Cómo ejecutar
Requisitos: Python 3.10+ y `pygame` (solo para el cliente).

Se necesitan 3 terminales, todas desde la carpeta del proyecto:

```bash
python -m servidor.main                    # 1. servidor (puerto 5050)
python -m cliente.main                     # 2. jugador 1
python -m cliente.main --ip 192.168.1.20   # 3. jugador 2 (IP del servidor)


Controles: Espacio / ↑ / W / click / toque para saltar. 


- **Servidor autoritativo:** los clientes solo envían *entradas* (`saltar`). Toda la física, colisiones y puntajes se calculan en el servidor, así que nadie puede mandar posiciones falsas y la partida no depende de la conexión de un jugador en particular (en Pong el anfitrión era el que mandaba).
- **Cliente:** dibuja. Recibe snapshots a 30/s e **interpola** entre ellos para mostrarlos a 60 FPS.
- **Hilos:** un hilo por cliente para leer, uno de escritura por cliente (con cola, para que un cliente lento no frene el juego) y un hilo del bucle de juego. El estado compartido está protegido por un `Lock`.
- **TCP con `TCP_NODELAY`** (sin esperas de Nagle). Pasar a UDP queda como mejora posible.
