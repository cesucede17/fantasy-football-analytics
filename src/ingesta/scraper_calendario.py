"""Scraping diario del calendario completo de LaLiga (todas las jornadas,
jugadas y por jugar) desde futbolfantasy.com.

A diferencia de precios_diarios (append-only), aquí interesa tener siempre
la foto completa del calendario — con los resultados que se van cerrando
cada jornada — así que se sobrescribe la pestaña entera cada día, igual que
estado_forma.

Es la base de datos para el historial de enfrentamientos, la racha
reciente y la clasificación actual que usa `src.analisis.enfrentamientos`.
Sin resultados reales no hay con qué calcular nada de eso.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

URL_CALENDARIO = "https://www.futbolfantasy.com/laliga/calendario"

USER_AGENT = (
    "FantasyLaligaBot/1.0 (uso personal, 1 peticion/dia; "
    "contacto: suelacesar17@gmail.com)"
)


@dataclass
class PartidoCalendario:
    temporada: str
    jornada: int
    fecha: str
    equipo_local: str
    equipo_visitante: str
    goles_local: int | None
    goles_visitante: int | None
    jugado: bool


def _temporada(soup: BeautifulSoup) -> str:
    titulo = soup.select_one("h1.title")
    texto = titulo.get_text(strip=True) if titulo else ""
    m = re.search(r"(\d{4}/\d{2})", texto)
    return m.group(1) if m else ""


def _resultado(el) -> tuple[int | None, int | None]:
    nodo = el.select_one(".resultado")
    if not nodo:
        return None, None
    texto = nodo.get_text(strip=True)
    m = re.match(r"(\d+)\s*-\s*(\d+)", texto)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _fecha(el) -> str:
    nodo = el.select_one(".date")
    return nodo.get_text(" ", strip=True) if nodo else ""


def obtener_calendario() -> list[PartidoCalendario]:
    """Descarga y parsea el calendario completo. Una petición, nada más."""
    resp = requests.get(URL_CALENDARIO, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "lxml")
    seccion = soup.select_one("section.mod.lista.partidos")
    if seccion is None:
        raise RuntimeError(
            "No se encontró la sección de partidos — la web pudo haber "
            "cambiado su estructura. Revisar scraper_calendario.py."
        )

    temporada = _temporada(soup)
    partidos: list[PartidoCalendario] = []
    jornada_actual = 0

    for el in seccion.find_all(["h3", "a"], recursive=True):
        if el.name == "h3":
            m = re.search(r"Jornada\s*(\d+)", el.get_text(strip=True))
            if m:
                jornada_actual = int(m.group(1))
            continue

        # el.name == "a" -> fila de partido
        if "partido" not in (el.get("class") or []):
            continue
        local_img = el.select_one(".equipo.local img")
        visitante_img = el.select_one(".equipo.visitante img")
        if local_img is None or visitante_img is None:
            continue
        goles_local, goles_visitante = _resultado(el)
        partidos.append(
            PartidoCalendario(
                temporada=temporada,
                jornada=jornada_actual,
                fecha=_fecha(el),
                equipo_local=local_img.get("alt", ""),
                equipo_visitante=visitante_img.get("alt", ""),
                goles_local=goles_local,
                goles_visitante=goles_visitante,
                jugado=goles_local is not None,
            )
        )

    if not partidos:
        raise RuntimeError(
            "Se encontró la sección de partidos pero no se extrajo ningún "
            "partido — revisar selectores en scraper_calendario.py."
        )
    return partidos


def a_filas(partidos: list[PartidoCalendario]) -> list[list]:
    return [
        [
            p.temporada, p.jornada, p.fecha, p.equipo_local, p.equipo_visitante,
            p.goles_local if p.goles_local is not None else "",
            p.goles_visitante if p.goles_visitante is not None else "",
            "si" if p.jugado else "no",
        ]
        for p in partidos
    ]


def main() -> None:
    from src.alertas.telegram import notificar_fallo
    from src.storage.sheets import leer_calendario_resultados, sobrescribir_calendario_resultados

    try:
        partidos = obtener_calendario()
        temporada_actual = partidos[0].temporada if partidos else ""

        # Esta pasada solo ve la temporada en curso — si se sobrescribiera
        # sin más, se perdería el histórico de temporadas anteriores
        # (backfill_historico_h2h.py) que usa el historial de
        # enfrentamientos. Se conservan las filas de otras temporadas tal
        # cual y se reemplazan solo las de esta.
        otras_temporadas = [
            [f.get("temporada"), f.get("jornada"), f.get("fecha"), f.get("equipo_local"), f.get("equipo_visitante"),
             f.get("goles_local"), f.get("goles_visitante"), f.get("jugado")]
            for f in leer_calendario_resultados()
            if f.get("temporada") != temporada_actual
        ]
        sobrescribir_calendario_resultados(otras_temporadas + a_filas(partidos))
        jugados = sum(1 for p in partidos if p.jugado)
        print(f"OK: {len(partidos)} partidos de {temporada_actual} ({jugados} jugados) guardados en calendario_resultados.")
    except Exception as err:
        notificar_fallo("scraper_calendario", err)
        raise


if __name__ == "__main__":
    main()
