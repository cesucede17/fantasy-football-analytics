"""Puntos de LaLiga Fantasy Oficial para el pool ENTERO de jugadores (no solo
los seguidos en mi_plantilla/watchlist/mercado_diario, a diferencia de
scraper_perfil.puntos_jornada) — base para el scouting de chollos (paso 4
del brainstorming de decisión, ver docs/04-bitacora.md).

Fuente: futbolfantasy.com/analytics/laliga-fantasy/puntos — mismo patrón que
scraper_precios.py (una sola página, cada jugador es un `<tr
class="elemento_jugador">` con los datos ya calculados como atributos data-*,
servido en HTML sin necesitar ejecutar JS). Una petición al día para los
~525 jugadores del pool, dentro de las reglas de scraping de CLAUDE.md.

A propósito NO se usa el `data-ratio` (Valor/Punto) que ya trae la propia
página: se prefiere recalcular "puntos por millón" en el cliente a partir
de precios_diarios (mismo valor de mercado que ya usa el resto de la web,
misma fórmula que estadisticas.js) en vez de fiarse de una definición ajena
de "valor" que podría no coincidir con la que ya usamos (¿de compra? ¿de
cláusula? ¿de hoy?). Por eso esta pestaña solo guarda puntos, no valor.

Solo trae puntos de TEMPORADA y de los últimos 3/5 partidos — a diferencia
de puntos_jornada, no hay desglose jornada a jornada aquí (esta fuente no
lo ofrece a nivel de pool completo, solo en la ficha individual). Son dos
fuentes complementarias, no una sustituye a la otra.

Es una foto del estado actual (como estado_forma), no histórico
acumulativo: cada pasada sobrescribe la pestaña entera.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

URL_PUNTOS_POOL = "https://www.futbolfantasy.com/analytics/laliga-fantasy/puntos"

USER_AGENT = (
    "FantasyLaligaBot/1.0 (uso personal, 1 peticion/dia; "
    "contacto: suelacesar17@gmail.com)"
)


@dataclass
class PuntosJugadorPool:
    fecha: str
    jugador: str
    equipo: str
    posicion: str
    puntos_temporada: int
    puntos_ultimos3: int
    puntos_ultimos5: int
    media: float
    partidos_jugados: int


def _texto_equipo(fila) -> str:
    equipo_div = fila.select_one(".player-equipo")
    if equipo_div is None:
        return ""
    span = equipo_div.find("span")
    if span and span.get_text(strip=True):
        return span.get_text(strip=True)
    img = equipo_div.find("img")
    return img.get("alt", "") if img else ""


def _texto_nombre(fila) -> str:
    nombre_a = fila.select_one(".player-name")
    if nombre_a is None:
        return fila.get("data-nombre", "").title()
    span = nombre_a.find("span")
    return span.get_text(strip=True) if span else nombre_a.get_text(strip=True)


def _entero(fila, atributo: str) -> int:
    try:
        return int(float(fila.get(atributo, "0") or "0"))
    except ValueError:
        return 0


def _decimal(fila, atributo: str) -> float:
    try:
        return float(fila.get(atributo, "0") or "0")
    except ValueError:
        return 0.0


def obtener_puntos_pool() -> list[PuntosJugadorPool]:
    """Descarga y parsea la página de puntos. Una petición, nada más."""
    resp = requests.get(URL_PUNTOS_POOL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    # Igual que scraper_precios: pasar bytes crudos para que BeautifulSoup
    # detecte bien el UTF-8 real a partir del <meta charset>, en vez del
    # Latin-1 que asume requests cuando el servidor no declara charset.
    soup = BeautifulSoup(resp.content, "lxml")
    filas = soup.select("tr.elemento_jugador")
    if not filas:
        raise RuntimeError(
            "No se encontraron filas de jugadores — la web pudo haber cambiado "
            "su estructura. Revisar scraper_puntos_pool.py."
        )

    fecha = dt.date.today().isoformat()
    jugadores = [
        PuntosJugadorPool(
            fecha=fecha,
            jugador=_texto_nombre(fila),
            equipo=_texto_equipo(fila),
            posicion=fila.get("data-posicion", ""),
            puntos_temporada=_entero(fila, "data-puntostemporada"),
            puntos_ultimos3=_entero(fila, "data-puntos3"),
            puntos_ultimos5=_entero(fila, "data-puntos5"),
            media=_decimal(fila, "data-mediatemporada"),
            partidos_jugados=_entero(fila, "data-temporada"),
        )
        for fila in filas
    ]
    return jugadores


def a_filas(jugadores: list[PuntosJugadorPool]) -> list[list]:
    return [
        [j.fecha, j.jugador, j.equipo, j.posicion, j.puntos_temporada, j.puntos_ultimos3, j.puntos_ultimos5, j.media, j.partidos_jugados]
        for j in jugadores
    ]


def main() -> None:
    from src.alertas.telegram import notificar_fallo
    from src.storage.sheets import sobrescribir_pool_puntos

    try:
        datos = obtener_puntos_pool()
        sobrescribir_pool_puntos(a_filas(datos))
        print(f"OK: {len(datos)} jugadores escritos en pool_puntos.")
    except Exception as err:  # noqa: BLE001 — sí, capturamos todo: es el job diario.
        notificar_fallo("scraper_puntos_pool", err)
        raise


if __name__ == "__main__":
    main()
