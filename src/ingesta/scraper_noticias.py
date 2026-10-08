"""Scraping diario de lesionados y sancionados desde futbolfantasy.com.

Guarda una fila por incidencia activa cada día (append-only, igual que
precios_diarios) y avisa por Telegram solo cuando la incidencia es nueva
Y afecta a un jugador de mi_plantilla o watchlist — así no se spamea cada
día con la misma lesión ya conocida.

Alineaciones probables queda pendiente: la web las separa por partido con
URLs por jornada en vez de un listado único, hace falta otra pasada de
reconocimiento para esa fuente.
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
    "FantasyLaligaBot/1.0 (uso personal, 1 peticion/dia; "
    "contacto: suelacesar17@gmail.com)"
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
