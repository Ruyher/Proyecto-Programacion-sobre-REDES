# Flappy Hornero Online

Flappy Hornero para dos jugadores en red. Combina la temática y la mecánica de *Flappy Hornero* con la idea cliente-servidor de *Pong*, corrigiendo sus puntos débiles.

## Cómo ejecutar

Requisitos: Python 3.10+ y `pygame` (solo para el cliente).

```bash
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Se necesitan 3 terminales, todas desde la carpeta del proyecto:

```bash
python -m servidor.main                    # 1. servidor (puerto 5050)
python -m cliente.main                     # 2. jugador 1
python -m cliente.main --ip 192.168.1.20   # 3. jugador 2 (IP del servidor)
```

Controles: **Espacio / ↑ / W / click / toque** para saltar. Al terminar la partida, la misma acción pide la revancha (empieza cuando los dos la piden).
Si el servidor corre en otra máquina, el puerto `5050/TCP` tiene que estar abierto en su firewall.

## Arquitectura

```
 Cliente 1 ──┐                    ┌── Cliente 2
  (entrada)  │   TCP / JSON\n     │  (entrada)
             ▼                    ▼
           ┌──────────────────────────┐
           │        SERVIDOR          │
           │  simula la física a 60Hz │
           │  difunde estado a 30Hz   │
           └──────────────────────────┘
```

- **Servidor autoritativo:** los clientes solo envían *entradas* (`saltar`). Toda la física, colisiones y puntajes se calculan en el servidor, así que nadie puede mandar posiciones falsas y la partida no depende de la conexión de un jugador en particular (en Pong el anfitrión era el que mandaba).
- **Cliente:** dibuja. Recibe snapshots a 30/s e **interpola** entre ellos para mostrarlos a 60 FPS.
- **Hilos:** un hilo por cliente para leer, uno de escritura por cliente (con cola, para que un cliente lento no frene el juego) y un hilo del bucle de juego. El estado compartido está protegido por un `Lock`.
- **TCP con `TCP_NODELAY`** (sin esperas de Nagle). Pasar a UDP queda como mejora posible.

## Protocolo

JSON, un mensaje por línea (`\n`). Todo mensaje lleva `tipo`. El receptor reensambla las líneas con un buffer, porque TCP es un flujo y un `recv` puede traer medio mensaje o varios juntos.

| Dirección | `tipo` | Contenido |
|---|---|---|
| C → S | `saltar` | — |
| C → S | `reiniciar` | pide revancha (solo vale cuando la partida terminó) |
| S → C | `asignacion` | `jugador`: 1 o 2 (el primer lugar libre) |
| S → C | `sala_llena` | se cierra la conexión |
| S → C | `inicio` | empieza una partida (con cuenta regresiva de 3 s) |
| S → C | `estado` | `fase`, `cuenta`, `jugadores{y,vivo,puntaje}`, `termos[{id,x,sup}]`, `ganador` |
| S → C | `desconexion` | `jugador` que se fue; la partida se corta y el que queda espera rival |

Las líneas que no son JSON válido o no tienen `tipo` se ignoran sin cortar la conexión. Una línea de más de 64 KB sin terminador corta esa conexión.

## Estructura

```
comun/      config.py (constantes), protocolo.py (codificar/decodificar)
servidor/   juego.py (lógica pura, sin red), main.py (sockets e hilos)
cliente/    red.py (conexión, sin Pygame), interpolacion.py, main.py (Pygame)
assets/     sprites
tests/      unittest
```

## Tests

```bash
python -m unittest discover -s tests -t . -v
```

Cubren el protocolo (mensajes partidos, pegados, basura), la lógica del juego (puntaje, fin, semilla determinista), la interpolación y la red de punta a punta con un servidor y clientes reales por sockets locales (asignación, sala llena, desconexión, reutilización de lugar, revancha).
El dibujado de Pygame no tiene tests automáticos: se prueba jugando.

## Ideas para seguir

- Power-ups como los de Pong (los eventos tendrían su propio `tipo`).
- Modo versus (un carril por jugador) además del cooperativo actual.
- Salas múltiples y nombres de jugador.
- Probar UDP para el estado y comparar latencia contra TCP.
