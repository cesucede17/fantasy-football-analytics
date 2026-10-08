"""Daily scraping of market values from public websites.

Fallback source if the API path doesn't pan out, and the main source of
global prices either way.

Rules: one pass per day, respect robots.txt, identifiable user-agent.
Every player in the futbolfantasy pool is stored (~534) — that's already
the pool filtered down to players relevant for Fantasy, not the full ~1,600
across LaLiga. The full roster is needed for the by-team search and
autocomplete.

Current source: futbolfantasy.com/analytics/laliga-fantasy/mercado. The
page returns each player as a `<tr class="elemento_jugador">` row with all
the data already computed (value, 1/7/14/30-day deltas) as data-* attributes,
in server-rendered HTML (no JS execution needed).
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

URL_MERCADO = "https://www.futbolfantasy.com/analytics/laliga-fantasy/mercado"
URL_DETALLE_JUGADOR = "https://www.futbolfantasy.com/analytics/laliga-fantasy/mercado/detalle/{id}?perfil=1"

USER_AGENT = (
    "FantasyLaligaBot/1.0 (personal use, 1 request/day; "
    "contact: suelacesar17@gmail.com)"
)


@dataclass
class PrecioJugador:
    fecha: str
    jugador_id: str
    nombre: str
    equipo: str
    posicion: str
    valor: int
    delta_1d: int
    delta_7d: int
    puntos_acum: str = ""  # not available from this source; left empty


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
    valor = fila.get(atributo, "0")
    try:
        return int(valor)
    except ValueError:
        return 0


def obtener_precios() -> list[PrecioJugador]:
    """Downloads and parses the market page. One request, nothing more."""
    resp = requests.get(URL_MERCADO, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    # requests assumes Latin-1 when the server doesn't declare a charset in
    # the header; this site is actually UTF-8. Passing raw bytes lets
    # BeautifulSoup detect it correctly from the HTML's own <meta charset>.
    soup = BeautifulSoup(resp.content, "lxml")
    filas = soup.select("tr.elemento_jugador")
    if not filas:
        raise RuntimeError(
            "No player rows found — the site may have changed its "
            "structure. Check scraper_precios.py."
        )

    fecha = dt.date.today().isoformat()
    jugadores = [
        PrecioJugador(
            fecha=fecha,
            jugador_id=fila.get("data-id", ""),
            nombre=_texto_nombre(fila),
            equipo=_texto_equipo(fila),
            posicion=fila.get("data-posicion", ""),
            valor=_entero(fila, "data-valor"),
            delta_1d=_entero(fila, "data-diferencia1"),
            delta_7d=_entero(fila, "data-diferencia7"),
        )
        for fila in filas
    ]

    jugadores.sort(key=lambda j: j.valor, reverse=True)
    return jugadores


def valor_historico_jugador(jugador_id: str, fecha_iso: str) -> int | None:
    """A player's market value on a specific date, taken from the 30-day
    history exposed on the player's market detail page (not available in
    the main table, only in this detail view). Returns None if the date
    falls outside that 30-day window or isn't found."""
    try:
        resp = requests.get(
            URL_DETALLE_JUGADOR.format(id=jugador_id),
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None

    fecha = dt.date.fromisoformat(fecha_iso)
    patron = re.compile(
        r'player_chartjs_30\.push\(\{date:\s*"' + fecha.strftime("%d/%m") + r'",\s*value:\s*(\d+)\}\)'
    )
    m = patron.search(resp.text)
    return int(m.group(1)) if m else None


def a_filas(jugadores: list[PrecioJugador]) -> list[list]:
    """Converts to flat lists, in `precios_diarios`'s column order."""
    return [
        [j.fecha, j.jugador_id, j.nombre, j.equipo, j.posicion, j.valor, j.delta_1d, j.delta_7d, j.puntos_acum]
        for j in jugadores
    ]


def main() -> None:
    from src.alertas.telegram import notificar_fallo
    from src.storage.sheets import append_precios_diarios

    try:
        datos = obtener_precios()
        append_precios_diarios(a_filas(datos))
        print(f"OK: {len(datos)} players written to precios_diarios.")
    except Exception as err:  # noqa: BLE001 — yes, we catch everything: it's the daily job.
        notificar_fallo("scraper_precios", err)
        raise


if __name__ == "__main__":
    main()
