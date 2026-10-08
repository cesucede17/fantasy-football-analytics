"""Official LaLiga Fantasy points for the ENTIRE player pool (not just the
ones tracked in mi_plantilla/watchlist/mercado_diario, unlike
scraper_perfil.puntos_jornada) — the base data for bargain scouting
(decision brainstorm step 4, see docs/04-bitacora.md).

Source: futbolfantasy.com/analytics/laliga-fantasy/puntos — same pattern as
scraper_precios.py (a single page, each player is a `<tr
class="elemento_jugador">` with the data already computed as data-*
attributes, server-rendered HTML, no JS execution needed). One request per
day for the ~525 players in the pool, within CLAUDE.md's scraping rules.

The page's own `data-ratio` (value/point) is deliberately NOT used: it's
preferable to recompute "points per million" client-side from
precios_diarios (the same market value already used by the rest of the
dashboard, the same formula as estadisticas.js) rather than trust someone
else's definition of "value" that might not match the one already in use
(purchase price? release clause? today's value?). That's why this tab only
stores points, not value.

Only carries SEASON points and the last 3/5 matches — unlike
puntos_jornada, there's no matchday-by-matchday breakdown here (this source
doesn't offer that at the full-pool level, only on the individual player
page). These are two complementary sources, neither replaces the other.

This is a snapshot of current status (like estado_forma), not a cumulative
history: every run overwrites the whole tab.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

URL_PUNTOS_POOL = "https://www.futbolfantasy.com/analytics/laliga-fantasy/puntos"

USER_AGENT = (
    "FantasyLaligaBot/1.0 (personal use, 1 request/day; "
    "contact: suelacesar17@gmail.com)"
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
    """Downloads and parses the points page. One request, nothing more."""
    resp = requests.get(URL_PUNTOS_POOL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    # Same as scraper_precios: pass raw bytes so BeautifulSoup correctly
    # detects the real UTF-8 encoding from <meta charset>, instead of the
    # Latin-1 requests assumes when the server doesn't declare a charset.
    soup = BeautifulSoup(resp.content, "lxml")
    filas = soup.select("tr.elemento_jugador")
    if not filas:
        raise RuntimeError(
            "No player rows found — the site may have changed its "
            "structure. Check scraper_puntos_pool.py."
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
        print(f"OK: {len(datos)} players written to pool_puntos.")
    except Exception as err:  # noqa: BLE001 — yes, we catch everything: it's the daily job.
        notificar_fallo("scraper_puntos_pool", err)
        raise


if __name__ == "__main__":
    main()
