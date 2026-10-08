"""Scraping diario de valores de mercado desde webs públicas.

Fuente de respaldo si la vía API no sale, y fuente principal de precios globales
en cualquier caso.

Reglas: una pasada al día, respetar robots.txt, user-agent identificable.
Se guardan todos los jugadores del pool de futbolfantasy (~534) — es el pool
ya filtrado a los relevantes para Fantasy, no los ~1.600 de LaLiga completa.
Hace falta el roster completo para el buscador por equipo y el autocompletado.

Fuente actual: futbolfantasy.com/analytics/laliga-fantasy/mercado. La página
trae cada jugador como una fila `<tr class="elemento_jugador">` con todos los
datos ya calculados (valor, diferencias en 1/7/14/30 días) como atributos
data-*, en HTML servido por el servidor (sin necesidad de ejecutar JS).
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
    "FantasyLaligaBot/1.0 (uso personal, 1 peticion/dia; "
    "contacto: suelacesar17@gmail.com)"
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
    puntos_acum: str = ""  # no disponible en esta fuente; se deja vacío


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
    """Descarga y parsea la página de mercado. Una petición, nada más."""
    resp = requests.get(URL_MERCADO, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    # requests asume Latin-1 si el servidor no declara charset en la cabecera;
    # esta web es UTF-8 real. Pasar bytes crudos deja que BeautifulSoup lo
    # detecte bien a partir del <meta charset> del propio HTML.
    soup = BeautifulSoup(resp.content, "lxml")
    filas = soup.select("tr.elemento_jugador")
    if not filas:
        raise RuntimeError(
            "No se encontraron filas de jugadores — la web pudo haber cambiado "
            "su estructura. Revisar scraper_precios.py."
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
    """Valor de mercado de un jugador en una fecha concreta, sacado del
    histórico de 30 días que expone la ficha de mercado del jugador (no
    aparece en la tabla general, solo en esta vista de detalle). Devuelve
    None si la fecha cae fuera de esos 30 días o no se encuentra."""
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
    """Convierte a listas planas, en el orden de columnas de `precios_diarios`."""
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
        print(f"OK: {len(datos)} jugadores escritos en precios_diarios.")
    except Exception as err:  # noqa: BLE001 — sí, capturamos todo: es el job diario.
        notificar_fallo("scraper_precios", err)
        raise


if __name__ == "__main__":
    main()
