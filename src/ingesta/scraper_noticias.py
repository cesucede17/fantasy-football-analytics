"""Daily scraping of injuries and suspensions from futbolfantasy.com.

Stores one row per active incident each day (append-only, like
precios_diarios) and alerts via Telegram only when the incident is new
AND affects a player in mi_plantilla or the watchlist — so it doesn't spam
the same already-known injury every day.

Probable lineups are still pending: the site splits them by match with
per-matchday URLs instead of a single listing, so this source needs its own
reconnaissance pass.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from src.textutil import normalizar

URL_LESIONADOS = "https://www.futbolfantasy.com/laliga/lesionados"
URL_SANCIONADOS = "https://www.futbolfantasy.com/laliga/sancionados"

USER_AGENT = (
    "FantasyLaligaBot/1.0 (personal use, 1 request/day; "
    "contact: suelacesar17@gmail.com)"
)


@dataclass
class IncidenciaJugador:
    fecha: str
    jugador: str
    tipo: str  # "lesion" | "sancion"
    detalle: str
    duracion: str = ""


def _texto(el, selector: str) -> str:
    nodo = el.select_one(selector)
    return nodo.get_text(strip=True) if nodo else ""


def obtener_lesionados() -> list[IncidenciaJugador]:
    resp = requests.get(URL_LESIONADOS, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")
    hoy = dt.date.today().isoformat()

    incidencias = []
    for el in soup.select(".elemento.lesionado"):
        jugador = _texto(el, "a.jugador")
        if not jugador:
            continue
        motivo = _texto(el, ".comentario span.lesion")
        duracion = _texto(el, ".comentario span[class^='gravedad']")
        incidencias.append(IncidenciaJugador(hoy, jugador, "lesion", motivo, duracion))
    return incidencias


def obtener_sancionados() -> list[IncidenciaJugador]:
    resp = requests.get(URL_SANCIONADOS, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")
    hoy = dt.date.today().isoformat()

    incidencias = []
    for el in soup.select(".elemento.sancionado"):
        jugador = _texto(el, "a.jugador")
        if not jugador:
            continue
        motivo = _texto(el, "span.sancion")
        incidencias.append(IncidenciaJugador(hoy, jugador, "sancion", motivo))
    return incidencias


def a_filas(incidencias: list[IncidenciaJugador]) -> list[list]:
    return [[i.fecha, i.jugador, i.tipo, i.detalle, i.duracion] for i in incidencias]


def _nombres_seguidos(mi_plantilla: list[dict], watchlist: list[dict]) -> set[str]:
    nombres = {normalizar(f.get("jugador", "")) for f in mi_plantilla}
    nombres |= {normalizar(f.get("jugador", "")) for f in watchlist}
    return {n for n in nombres if n}


def _es_seguido(jugador: str, nombres_seguidos: set[str]) -> bool:
    objetivo = normalizar(jugador)
    return any(objetivo in n or n in objetivo for n in nombres_seguidos)


def main() -> None:
    from src.alertas.telegram import enviar_mensaje, notificar_fallo
    from src.storage.sheets import (
        append_estado_jugadores,
        leer_estado_jugadores,
        leer_mi_plantilla,
        leer_watchlist,
    )

    try:
        incidencias = obtener_lesionados() + obtener_sancionados()

        historial = leer_estado_jugadores()
        ya_vistas = {(h.get("jugador"), h.get("tipo"), h.get("detalle")) for h in historial}
        nombres_seguidos = _nombres_seguidos(leer_mi_plantilla(), leer_watchlist())

        for inc in incidencias:
            if (inc.jugador, inc.tipo, inc.detalle) in ya_vistas:
                continue
            if not _es_seguido(inc.jugador, nombres_seguidos):
                continue
            emoji = "🚑" if inc.tipo == "lesion" else "🟥"
            texto = f"{emoji} {inc.jugador}: {inc.detalle}"
            if inc.duracion:
                texto += f" — {inc.duracion}"
            enviar_mensaje(texto)

        append_estado_jugadores(a_filas(incidencias))
    except Exception as err:
        notificar_fallo("scraper_noticias", err)
        raise


if __name__ == "__main__":
    main()
