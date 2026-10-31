"""Cliente Pygame de Flappy Hornero Online.

No simula nada: manda entradas, recibe snapshots (30/s) y los dibuja a 60 FPS
interpolando entre el snapshot anterior y el actual para que se vea fluido.

Uso:  python -m cliente.main [--ip 127.0.0.1] [--puerto 5050]
"""
import argparse
import os
import sys
import time

import pygame

from comun import config as C
from comun import protocolo as P
from cliente.interpolacion import interpolar
from cliente.red import CERRADA, ClienteRed

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELESTE = (112, 197, 206)
BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)
SUELO_AMARILLO = (222, 216, 149)
PASTO = (115, 191, 46)
COLOR_JUGADOR = {1: (255, 255, 100), 2: (100, 255, 255)}
INTERVALO_SNAP = 1.0 / C.SNAPSHOT_HZ


class App:
    def __init__(self, ip=None, puerto=C.PUERTO, max_frames=None):
        pygame.init()
        self.pantalla = pygame.display.set_mode((C.ANCHO, C.ALTO))
        pygame.display.set_caption("Flappy Hornero Online")
        self.reloj = pygame.time.Clock()
        self.f_chica = pygame.font.Font(None, 26)
        self.f_grande = pygame.font.Font(None, 40)
        self._cargar_recursos()
        self.ip = ip
        self.puerto = puerto
        self.max_frames = max_frames  # solo para pruebas automáticas
        self.frames = 0
        self.snapshots_recibidos = 0

    def _cargar_recursos(self):
        def cargar(nombre, tam=None):
            try:
                img = pygame.image.load(os.path.join(RAIZ, "assets", nombre)).convert_alpha()
                return pygame.transform.scale(img, tam) if tam else img
            except (pygame.error, FileNotFoundError):
                return None

        self.img_hornero = cargar("hornero.png", (C.HORNERO_ANCHO, C.HORNERO_ALTO))
        self.img_termo_inf = cargar("termo.png")
        self.img_termo_sup = cargar("termo_techo.png")
        self._cache_termos = {}  # (tipo, alto) -> Surface ya escalada

    # ------------------------------------------------------------------ flujo
    def ejecutar(self):
        error = None
        while True:
            ip = self.ip or self.menu_ip(error)
            if ip is None:
                break
            red = ClienteRed()
            try:
                red.conectar(ip, self.puerto)
            except OSError as e:
                error = f"No se pudo conectar: {e.strerror or e}"
                if self.ip:  # modo no interactivo
                    print(error, file=sys.stderr)
                    break
                continue
            error = self.partida(red)
            red.cerrar()
            if error is None or self.ip:
                break
        pygame.quit()

    def menu_ip(self, error=None):
        texto = "127.0.0.1"
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return None
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_RETURN and texto.strip():
                        return texto.strip()
                    if e.key == pygame.K_ESCAPE:
                        return None
                    if e.key == pygame.K_BACKSPACE:
                        texto = texto[:-1]
                    elif e.unicode and (e.unicode.isalnum() or e.unicode in ".-") and len(texto) < 40:
                        texto += e.unicode
            self.pantalla.fill(CELESTE)
            self._centrado("FLAPPY HORNERO ONLINE", self.f_grande, 150)
            self._centrado("IP del servidor:", self.f_chica, 250, BLANCO)
            self._centrado(texto + "_", self.f_grande, 285, COLOR_JUGADOR[1])
            self._centrado("Enter para conectar", self.f_chica, 340, BLANCO)
            if error:
                self._centrado(error, self.f_chica, 400, (200, 40, 40))
            pygame.display.flip()
            self.reloj.tick(30)

    def partida(self, red: ClienteRed):
        """Bucle de una conexión. Devuelve un texto de error, o None si se cerró la ventana."""
        mi_id = None
        aviso = None
        esperando = True
        prev = curr = None
        t_curr = time.monotonic()

        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return None
                es_salto = (e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w)) \
                    or e.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN)
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return None
                if es_salto:
                    if curr and curr["fase"] == "FIN":
                        red.enviar({"tipo": P.REINICIAR})
                    else:
                        red.enviar({"tipo": P.SALTAR})

            for msg in red.sacar_mensajes():
                tipo = msg["tipo"]
                if tipo == P.ASIGNACION:
                    mi_id = msg.get("jugador")
                elif tipo == P.SALA_LLENA:
                    return "La sala está llena."
                elif tipo == P.INICIO:
                    esperando, aviso, prev, curr = False, None, None, None
                elif tipo == P.ESTADO:
                    prev, curr = curr, msg
                    t_curr = time.monotonic()
                    self.snapshots_recibidos += 1
                elif tipo == P.DESCONEXION:
                    esperando, prev, curr = True, None, None
                    aviso = "Tu rival se desconectó. Esperando otro jugador..."
                elif tipo == CERRADA:
                    return "Se perdió la conexión con el servidor."

            alpha = min(1.0, (time.monotonic() - t_curr) / INTERVALO_SNAP)
            self.dibujar(mi_id, esperando, aviso, prev, curr, alpha)
            pygame.display.flip()
            self.reloj.tick(C.FPS_CLIENTE)

            self.frames += 1
            if self.max_frames and self.frames >= self.max_frames:
                return None

    # ------------------------------------------------------------------ dibujo
    def dibujar(self, mi_id, esperando, aviso, prev, curr, alpha):
        self.pantalla.fill(CELESTE)
        if curr:
            ys, termos = interpolar(prev, curr, alpha)
            for x, sup in termos:
                self._dibujar_termo(x, sup)
        self._dibujar_suelo()

        if curr:
            for i, y in ys.items():
                if curr["jugadores"][str(i)]["vivo"]:
                    if self.img_hornero:
                        self.pantalla.blit(self.img_hornero, (C.X_JUGADOR[i], y))
                    else:
                        pygame.draw.rect(self.pantalla, (181, 101, 29),
                                         (C.X_JUGADOR[i], y, C.HORNERO_ANCHO, C.HORNERO_ALTO))
                    if i == mi_id:  # marca "vos sos este"
                        pygame.draw.polygon(self.pantalla, COLOR_JUGADOR[i], [
                            (C.X_JUGADOR[i] + 20, y - 4), (C.X_JUGADOR[i] + 14, y - 14),
                            (C.X_JUGADOR[i] + 26, y - 14)])
            for i in (1, 2):
                j = curr["jugadores"][str(i)]
                color = COLOR_JUGADOR[i] if j["vivo"] else (150, 150, 150)
                etiqueta = f"P{i}{' (vos)' if i == mi_id else ''}: {j['puntaje']}"
                self.pantalla.blit(self.f_chica.render(etiqueta, True, color), (15 if i == 1 else 210, 15))

        if esperando:
            self._velo()
            self._centrado(aviso or "Esperando rival...", self.f_chica, 290, BLANCO)
        elif curr and curr["fase"] == "CUENTA":
            self._centrado(str(curr["cuenta"]), self.f_grande, 270, BLANCO)
        elif curr and curr["fase"] == "FIN":
            self._velo()
            g = curr["ganador"]
            self._centrado("¡FIN DE LA PARTIDA!", self.f_grande, 200, BLANCO)
            self._centrado("Empate" if g == 0 else f"Ganó P{g}" + (" (vos)" if g == mi_id else ""),
                           self.f_chica, 260, BLANCO)
            self._centrado("Tocá o apretá espacio para revancha", self.f_chica, 330, BLANCO)

    def _dibujar_termo(self, x, sup):
        inf = C.ALTO - sup - C.HUECO
        for tipo, img, alto, y in (("sup", self.img_termo_sup, sup, 0),
                                   ("inf", self.img_termo_inf, inf, C.ALTO - inf)):
            if img:
                clave = (tipo, alto)
                if clave not in self._cache_termos:  # escalar una sola vez por altura
                    self._cache_termos[clave] = pygame.transform.scale(img, (C.TERMO_ANCHO, alto))
                self.pantalla.blit(self._cache_termos[clave], (x, y))
            else:
                pygame.draw.rect(self.pantalla, (44, 94, 59), (x, y, C.TERMO_ANCHO, alto))

    def _dibujar_suelo(self):
        pygame.draw.rect(self.pantalla, SUELO_AMARILLO, (0, C.ALTO - C.SUELO, C.ANCHO, C.SUELO))
        pygame.draw.rect(self.pantalla, PASTO, (0, C.ALTO - C.SUELO, C.ANCHO, 10))

    def _velo(self):
        s = pygame.Surface((C.ANCHO, C.ALTO))
        s.set_alpha(160)
        s.fill(NEGRO)
        self.pantalla.blit(s, (0, 0))

    def _centrado(self, texto, fuente, y, color=BLANCO):
        img = fuente.render(texto, True, color)
        self.pantalla.blit(img, (C.ANCHO // 2 - img.get_width() // 2, y))


def main():
    ap = argparse.ArgumentParser(description="Cliente de Flappy Hornero Online")
    ap.add_argument("--ip", help="IP del servidor (si se omite, se pide en pantalla)")
    ap.add_argument("--puerto", type=int, default=C.PUERTO)
    args = ap.parse_args()
    App(args.ip, args.puerto).ejecutar()


if __name__ == "__main__":
    main()
