"""Constantes compartidas por servidor y cliente.

Un único lugar para puerto, tamaños y física: así no vuelve a pasar que el
README, el servidor y el cliente usen puertos distintos.
"""

# --- Red ---
HOST_SERVIDOR = "0.0.0.0"
PUERTO = 5050
MAX_JUGADORES = 2

# --- Tiempo ---
TICK_HZ = 60          # simulación del servidor
SNAPSHOT_HZ = 30      # cuántos estados por segundo se envían a los clientes
SNAPSHOT_DIV = TICK_HZ // SNAPSHOT_HZ
FPS_CLIENTE = 60
CUENTA_TICKS = 3 * TICK_HZ  # cuenta regresiva antes de empezar

# --- Mundo ---
ANCHO = 400
ALTO = 600
SUELO = 50  # alto de la franja de suelo

# --- Hornero ---
HORNERO_ANCHO = 40
HORNERO_ALTO = 30
GRAVEDAD = 0.45
SALTO = -7.5
X_JUGADOR = {1: 60, 2: 100}
Y_INICIAL = {1: 200, 2: 350}

# --- Termos (obstáculos) ---
TERMO_ANCHO = 60
HUECO = 180
TERMO_VEL = 3
SUP_MIN = 50
SUP_MAX = 260
PRIMER_TERMO_X = ANCHO + 200
DIST_SPAWN = 220  # se crea un termo nuevo cuando el último pasó ANCHO - DIST_SPAWN
