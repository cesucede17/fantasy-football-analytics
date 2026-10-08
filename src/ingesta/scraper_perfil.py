"""Estado de forma por jugador (disponibilidad, probabilidad de titularidad,
riesgo de lesión, jerarquía) y puntos reales de LaLiga Fantasy por jornada
jugada — ambos salen de la misma ficha individual del jugador, así que se
scrapea una sola vez por jugador y se reparte en dos pestañas.

A diferencia de scraper_precios (una página con todos los jugadores) y
scraper_noticias (una página con todos los lesionados/sancionados), estos
datos solo existen en la ficha individual de cada jugador — una URL por
jugador. Por eso NO se scrapea el pool entero (~660 peticiones/día sería
agresivo y rompe la regla de scraping de CLAUDE.md): solo se consulta a los
jugadores en mi_plantilla, watchlist y mercado_diario, que son los que de
verdad importan para decidir.

estado_forma no es append-only como precios_diarios: es una foto del estado
actual, así que cada ejecución sobrescribe la pestaña entera (no interesa
acumular histórico de jerarquía/riesgo día a día).

puntos_jornada SÍ es append-only (una jornada jugada es un hecho que no
cambia) — pero la ficha del jugador siempre muestra el historial completo de
jornadas jugadas hasta la fecha, así que cada pasada trae de nuevo jornadas
ya guardadas. El propio scraper hace el dedup contra lo que ya hay en la
pestaña antes de añadir nada. Efecto colateral útil: la primera vez que esto
se ejecuta rellena solas todas las jornadas ya jugadas de la temporada, sin
necesitar un backfill aparte.
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
    "FantasyLaligaBot/1.0 (uso personal, 1 peticion/dia; "
    "contacto: suelacesar17@gmail.com)"
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
    """Los 'cuadros' de estado no tienen clases estables por dato — se
    localizan por el texto de su etiqueta (ej. 'Riesgo les.', 'Titular')."""
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
    """Tabla de puntos por jornada de la ficha del jugador. La página
    reutiliza el mismo bloque para varios juegos de fantasy (Comunio,
    Biwenger, Mister...); cada partido trae un <span> por juego con la
    puntuación ya calculada — se coge solo el de clase "laliga-fantasy"
    (LaLiga Fantasy Oficial, el juego de este proyecto). Las filas de
    jornada real tienen atributo data-local ("1"=local, "0"=visitante); las
    filas de totales agregados (temporada, casa/fuera) no lo tienen, así
    que ese atributo basta para no confundirlas."""
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
    """Filtra las (jornada, jugador) que `puntos_jornada` ya tiene — la
    ficha del jugador siempre trae el historial completo, no solo lo nuevo."""
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
            f"OK: estado de forma actualizado para {len(estados)}/{len(nombres)} jugadores seguidos. "
            f"{len(filas_puntos_nuevas)} filas nuevas en puntos_jornada."
        )
    except Exception as err:
        notificar_fallo("scraper_perfil", err)
        raise


if __name__ == "__main__":
    main()
