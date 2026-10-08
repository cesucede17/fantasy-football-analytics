"""Per-player form status (availability, starting-lineup probability,
injury risk, squad hierarchy) and real LaLiga Fantasy points per matchday
played — both come from the same individual player page, so it's scraped
once per player and split across two tabs.

Unlike scraper_precios (one page with every player) and scraper_noticias
(one page with every injured/suspended player), this data only exists on
each player's individual profile page — one URL per player. That's why the
whole pool is NOT scraped (~660 requests/day would be aggressive and breaks
the scraping rule in CLAUDE.md): only players in mi_plantilla, the
watchlist, and mercado_diario are queried — the ones that actually matter
for decisions.

estado_forma isn't append-only like precios_diarios: it's a snapshot of
current status, so every run overwrites the whole tab (there's no value in
accumulating a day-by-day history of hierarchy/risk).

puntos_jornada IS append-only (a played matchday is a fact that doesn't
change) — but the player's page always shows the full history of matchdays
played to date, so every pass brings back matchdays already stored. The
scraper itself dedupes against what's already in the tab before adding
anything. Useful side effect: the first time this runs, it backfills every
matchday already played in the season on its own, no separate backfill
needed.
"""
from __future__ import annotations

import datetime as dt
import re
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from src.textutil import slug

URL_PERFIL = "https://www.futbolfantasy.com/jugadores/{slug}"

USER_AGENT = (
    "FantasyLaligaBot/1.0 (personal use, 1 request/day; "
    "contact: suelacesar17@gmail.com)"
)

PAUSA_ENTRE_PETICIONES_SEGUNDOS = 1.5


@dataclass
class EstadoForma:
    fecha: str
    jugador: str
    disponibilidad: str
    titular_jornada: str
    titular_probabilidad: str
    riesgo_lesion: str
    jerarquia: str


@dataclass
class PuntoJornada:
    jornada: int
    jugador: str
    puntos: float


def _texto(el, selector: str) -> str:
    nodo = el.select_one(selector)
    return nodo.get_text(strip=True) if nodo else ""


def _cuadro_con_texto(soup: BeautifulSoup, pista: str):
    """Status 'boxes' don't have stable classes per data point — they're
    located by their label's text instead (e.g. 'Riesgo les.', 'Titular')."""
    for cuadro in soup.select(".cuadro"):
        if pista.lower() in cuadro.get_text(" ", strip=True).lower():
            return cuadro
    return None


def obtener_pagina_jugador(nombre: str) -> BeautifulSoup | None:
    url = URL_PERFIL.format(slug=slug(nombre))
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return BeautifulSoup(resp.content, "lxml")


def estado_desde_pagina(soup: BeautifulSoup, nombre: str) -> EstadoForma:
    hoy = dt.date.today().isoformat()

    disponibilidad = _texto(soup, ".alturalesionfix span")

    cuadro_titular = _cuadro_con_texto(soup, "titular")
    titular_jornada = ""
    titular_probabilidad = ""
    if cuadro_titular:
        etiqueta = _texto(cuadro_titular, ".rs-cuadros-phone")
        titular_jornada = etiqueta.replace("Titular", "").strip()
        titular_probabilidad = _texto(cuadro_titular, ".probabilidad-widgetGr span")

    cuadro_riesgo = _cuadro_con_texto(soup, "riesgo les")
    riesgo_lesion = ""
    if cuadro_riesgo:
        divs = cuadro_riesgo.select("div")
        riesgo_lesion = divs[-1].get_text(strip=True) if divs else ""

    jerarquia = _texto(soup, ".jerarquia-value")

    return EstadoForma(
        fecha=hoy,
        jugador=nombre,
        disponibilidad=disponibilidad,
        titular_jornada=titular_jornada,
        titular_probabilidad=titular_probabilidad,
        riesgo_lesion=riesgo_lesion,
        jerarquia=jerarquia,
    )


def puntos_desde_pagina(soup: BeautifulSoup, nombre: str) -> list[PuntoJornada]:
    """Per-matchday points table from the player's page. The page reuses
    the same block for several fantasy games (Comunio, Biwenger, Mister...);
    each match row carries one <span> per game with its already-computed
    score — only the one with class "laliga-fantasy" is taken (the
    official LaLiga Fantasy game, this project's target). Real matchday
    rows carry a data-local attribute ("1"=home, "0"=away); aggregated
    total rows (season, home/away) don't, so that attribute alone is
    enough to avoid confusing the two."""
    filas = []
    for tr in soup.select("tr.plegado.plegable[data-local]"):
        jorn_td = tr.select_one("td.jorn-td")
        span_puntos = tr.select_one("td.data.points span.laliga-fantasy")
        if not jorn_td or not span_puntos:
            continue
        jornada_texto = jorn_td.get_text(strip=True)
        puntos_texto = span_puntos.get_text(strip=True).replace(",", ".")
        if not re.fullmatch(r"\d+", jornada_texto):
            continue
        try:
            puntos = float(puntos_texto)
        except ValueError:
            continue
        filas.append(PuntoJornada(jornada=int(jornada_texto), jugador=nombre, puntos=puntos))
    return filas


def _nombres_a_seguir() -> list[str]:
    from src.storage.sheets import leer_mercado_diario, leer_mi_plantilla, leer_watchlist

    nombres = set()
    for fila in leer_mi_plantilla() + leer_watchlist() + leer_mercado_diario():
        nombre = fila.get("jugador")
        if nombre:
            nombres.add(nombre)
    return sorted(nombres)


def a_filas(estados: list[EstadoForma]) -> list[list]:
    return [
        [e.fecha, e.jugador, e.disponibilidad, e.titular_jornada, e.titular_probabilidad, e.riesgo_lesion, e.jerarquia]
        for e in estados
    ]


def _puntos_nuevos(puntos: list[PuntoJornada], ya_guardados: set[tuple[str, str]]) -> list[list]:
    """Filters out the (matchday, player) pairs `puntos_jornada` already
    has — the player's page always brings the full history, not just what's
    new."""
    return [
        [p.jornada, p.jugador, p.puntos]
        for p in puntos
        if (str(p.jornada), p.jugador) not in ya_guardados
    ]


def main() -> None:
    from src.alertas.telegram import notificar_fallo
    from src.storage.sheets import append_puntos_jornada, leer_puntos_jornada, sobrescribir_estado_forma

    try:
        nombres = _nombres_a_seguir()
        ya_guardados = {(str(f.get("jornada")), f.get("jugador")) for f in leer_puntos_jornada()}

        estados = []
        puntos = []
        for i, nombre in enumerate(nombres):
            if i > 0:
                time.sleep(PAUSA_ENTRE_PETICIONES_SEGUNDOS)
            soup = obtener_pagina_jugador(nombre)
            if not soup:
                continue
            estados.append(estado_desde_pagina(soup, nombre))
            puntos.extend(puntos_desde_pagina(soup, nombre))

        sobrescribir_estado_forma(a_filas(estados))

        filas_puntos_nuevas = _puntos_nuevos(puntos, ya_guardados)
        append_puntos_jornada(filas_puntos_nuevas)

        print(
            f"OK: form status updated for {len(estados)}/{len(nombres)} tracked players. "
            f"{len(filas_puntos_nuevas)} new rows in puntos_jornada."
        )
    except Exception as err:
        notificar_fallo("scraper_perfil", err)
        raise


if __name__ == "__main__":
    main()
