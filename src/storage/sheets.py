"""Read/write access to Google Sheets via gspread.

precios_diarios is append-only: rows are never overwritten.

Authentication: a Google Cloud service account. Credentials arrive as JSON
(the full content, not a file path) in the GOOGLE_CREDENTIALS_JSON
environment variable — so it works the same way locally (.env) and in
GitHub Actions (secret). The sheet must be shared with that service
account's email (ends in @...iam.gserviceaccount.com) with Editor access.
"""
from __future__ import annotations

import json

import gspread
from google.oauth2.service_account import Credentials

from src.config import GOOGLE_CREDENTIALS_JSON, GOOGLE_SHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def _cliente() -> gspread.Client:
    if not GOOGLE_CREDENTIALS_JSON:
        raise RuntimeError(
            "GOOGLE_CREDENTIALS_JSON is missing (the service account's JSON "
            "content, not a file path)."
        )
    info = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _hoja(nombre_pestana: str):
    if not GOOGLE_SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID is missing.")
    return _cliente().open_by_key(GOOGLE_SHEET_ID).worksheet(nombre_pestana)


def _hoja_o_crear(nombre_pestana: str, cabecera: list[str]):
    """Like _hoja, but creates the tab with its header if it doesn't exist
    yet — so it doesn't have to be created by hand in the Sheet."""
    if not GOOGLE_SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID is missing.")
    libro = _cliente().open_by_key(GOOGLE_SHEET_ID)
    try:
        return libro.worksheet(nombre_pestana)
    except gspread.WorksheetNotFound:
        hoja = libro.add_worksheet(title=nombre_pestana, rows=1000, cols=max(len(cabecera), 1))
        hoja.append_row(cabecera, value_input_option="USER_ENTERED")
        return hoja


def append_precios_diarios(filas: list[list]) -> None:
    """Appends rows to `precios_diarios`. Never updates or overwrites."""
    if not filas:
        return
    _hoja("precios_diarios").append_rows(filas, value_input_option="USER_ENTERED")


def append_estado_jugadores(filas: list[list]) -> None:
    """Appends rows to `estado_jugadores` (injuries/suspensions). Append-only."""
    if not filas:
        return
    _hoja("estado_jugadores").append_rows(filas, value_input_option="USER_ENTERED")


def sobrescribir_estado_forma(filas: list[list]) -> None:
    """Fully replaces `estado_forma`: it's a snapshot of the tracked
    players' current status, not a history — unlike the append-only tabs,
    only the most recent value matters here."""
    hoja = _hoja("estado_forma")
    hoja.clear()
    cabecera = ["fecha", "jugador", "disponibilidad", "titular_jornada", "titular_probabilidad", "riesgo_lesion", "jerarquia"]
    hoja.append_row(cabecera, value_input_option="USER_ENTERED")
    if filas:
        hoja.append_rows(filas, value_input_option="USER_ENTERED")


def _asegurar_columna(nombre_pestana: str, columna: str) -> None:
    hoja = _hoja(nombre_pestana)
    cabecera = hoja.row_values(1)
    if columna not in cabecera:
        hoja.update_cell(1, len(cabecera) + 1, columna)


def actualizar_titulares_mi_plantilla(nombres_titulares: set[str]) -> None:
    """Marks which players in mi_plantilla are in the current starting
    lineup. The rest are treated as bench. Stored in a `titular` column,
    added to the tab the first time this is used."""
    _asegurar_columna("mi_plantilla", "titular")
    hoja = _hoja("mi_plantilla")
    valores = hoja.get_all_values()
    if len(valores) < 2:
        return
    cabecera = valores[0]
    idx_jugador = cabecera.index("jugador")
    idx_titular = cabecera.index("titular")
    for i, fila in enumerate(valores[1:], start=2):
        es_titular = fila[idx_jugador] in nombres_titulares
        hoja.update_cell(i, idx_titular + 1, "si" if es_titular else "")


def agregar_a_mi_plantilla(jugador: str, precio_compra: float, clausula: float, fecha_compra: str) -> None:
    _hoja("mi_plantilla").append_row(
        [jugador, precio_compra, fecha_compra, clausula, "", ""], value_input_option="USER_ENTERED"
    )


def eliminar_de_mi_plantilla(jugador: str) -> None:
    hoja = _hoja("mi_plantilla")
    valores = hoja.col_values(1)  # "jugador" column
    for i, nombre in enumerate(valores, start=1):
        if nombre == jugador:
            hoja.delete_rows(i)
            return


def agregar_a_mercado_diario(fecha: str, jugador: str, precio_salida: float, es_mio: bool) -> None:
    _hoja("mercado_diario").append_row(
        [fecha, jugador, precio_salida, "si" if es_mio else ""], value_input_option="USER_ENTERED"
    )


def eliminar_de_mercado_diario(jugador: str) -> None:
    hoja = _hoja("mercado_diario")
    valores = hoja.get_all_values()
    if len(valores) < 2:
        return
    idx_jugador = valores[0].index("jugador")
    for i, fila in enumerate(valores[1:], start=2):
        if fila[idx_jugador] == jugador:
            hoja.delete_rows(i)
            return


def resetear_mercado_diario() -> None:
    """Empties mercado_diario entirely, keeping the header. LaLiga
    Fantasy's real market rotates every day at 22:00 — without this,
    players from already-closed markets would keep piling up."""
    hoja = _hoja("mercado_diario")
    cabecera = hoja.row_values(1)
    hoja.clear()
    hoja.append_row(cabecera, value_input_option="USER_ENTERED")


def agregar_movimiento_liga(fecha: str, jugador: str, tipo: str, manager: str, importe: float) -> None:
    _hoja("movimientos_liga").append_row(
        [fecha, jugador, tipo, manager, importe], value_input_option="USER_ENTERED"
    )


def agregar_a_plantilla_rival(manager: str, jugador: str, precio_registro: float, fecha_registro: str) -> None:
    _hoja("plantillas_rivales").append_row(
        [manager, jugador, precio_registro, fecha_registro], value_input_option="USER_ENTERED"
    )


def eliminar_de_plantilla_rival(manager: str, jugador: str) -> None:
    hoja = _hoja("plantillas_rivales")
    valores = hoja.get_all_values()
    if len(valores) < 2:
        return
    cabecera = valores[0]
    idx_manager = cabecera.index("manager")
    idx_jugador = cabecera.index("jugador")
    for i, fila in enumerate(valores[1:], start=2):
        if fila[idx_manager] == manager and fila[idx_jugador] == jugador:
            hoja.delete_rows(i)
            return


def leer_plantillas_rivales() -> list[dict]:
    return leer_hoja("plantillas_rivales")


def leer_hoja(nombre_pestana: str) -> list[dict]:
    """Reads a whole tab as a list of dicts (row 1 = headers)."""
    return _hoja(nombre_pestana).get_all_records()


def leer_precios_diarios() -> list[dict]:
    return leer_hoja("precios_diarios")


def leer_mercado_diario() -> list[dict]:
    return leer_hoja("mercado_diario")


def leer_movimientos_liga() -> list[dict]:
    return leer_hoja("movimientos_liga")


def leer_mi_plantilla() -> list[dict]:
    return leer_hoja("mi_plantilla")


def leer_watchlist() -> list[dict]:
    return leer_hoja("watchlist")


def leer_estado_jugadores() -> list[dict]:
    return leer_hoja("estado_jugadores")


def leer_estado_forma() -> list[dict]:
    return leer_hoja("estado_forma")


CABECERA_PUNTOS_JORNADA = ["jornada", "jugador", "puntos"]


def append_puntos_jornada(filas: list[list]) -> None:
    """Appends rows to `puntos_jornada`. Append-only, like precios_diarios:
    a played matchday is a historical fact that doesn't change. The scraper
    (scraper_perfil) is responsible for not resending a matchday already
    stored for that player — no dedup happens here."""
    if not filas:
        return
    _hoja_o_crear("puntos_jornada", CABECERA_PUNTOS_JORNADA).append_rows(filas, value_input_option="USER_ENTERED")


def leer_puntos_jornada() -> list[dict]:
    try:
        return leer_hoja("puntos_jornada")
    except gspread.WorksheetNotFound:
        return []


CABECERA_CALENDARIO = [
    "temporada", "jornada", "fecha", "equipo_local", "equipo_visitante",
    "goles_local", "goles_visitante", "jugado",
]


def sobrescribir_calendario_resultados(filas: list[list]) -> None:
    """Fully replaces `calendario_resultados`: every pass brings the whole
    schedule (played and upcoming), so accumulating makes no sense — only
    the most recent snapshot matters, with results being settled as they
    happen."""
    hoja = _hoja_o_crear("calendario_resultados", CABECERA_CALENDARIO)
    hoja.clear()
    hoja.append_row(CABECERA_CALENDARIO, value_input_option="USER_ENTERED")
    if filas:
        hoja.append_rows(filas, value_input_option="USER_ENTERED")


def leer_calendario_resultados() -> list[dict]:
    try:
        return leer_hoja("calendario_resultados")
    except gspread.WorksheetNotFound:
        return []


CABECERA_CLASIFICACION_ANTERIOR = ["equipo", "posicion", "temporada"]


def sobrescribir_clasificacion_anterior(filas: list[list]) -> None:
    """Last season's final standings. Static reference data (never
    re-scraped): a starting point at the beginning of a season, while there
    aren't yet enough played matches to compute a real table."""
    hoja = _hoja_o_crear("clasificacion_anterior", CABECERA_CLASIFICACION_ANTERIOR)
    hoja.clear()
    hoja.append_row(CABECERA_CLASIFICACION_ANTERIOR, value_input_option="USER_ENTERED")
    if filas:
        hoja.append_rows(filas, value_input_option="USER_ENTERED")


def leer_clasificacion_anterior() -> list[dict]:
    try:
        return leer_hoja("clasificacion_anterior")
    except gspread.WorksheetNotFound:
        return []


CABECERA_POOL_PUNTOS = [
    "fecha", "jugador", "equipo", "posicion", "puntos_temporada",
    "puntos_ultimos3", "puntos_ultimos5", "media", "partidos_jugados",
]


def sobrescribir_pool_puntos(filas: list[list]) -> None:
    """Official LaLiga Fantasy points for the entire pool (scraper_puntos_pool),
    the base data for bargain scouting. A snapshot of current status, not a
    history (unlike puntos_jornada): every pass overwrites the whole tab,
    same as estado_forma.

    WATCH OUT when reading `media` back via leer_pool_puntos()/leer_hoja():
    this sheet is written correctly (Sheets genuinely stores 4.33), but
    gspread's get_all_records() reads in FORMATTED_VALUE mode with its own
    numericise step, which does NOT understand the Spanish decimal
    separator ("4,33" as the cell displays it) — it parses it as a
    thousands separator and returns 433. Verified by hand in the session
    where this was built (see docs/04-bitacora.md). Doesn't affect the web
    dashboard (Apps Script reads with getValues(), unaffected by this) or
    anything that exists in Python today (nothing reads `media` yet). If
    it's ever needed from Python, recompute it as
    `puntos_temporada / partidos_jugados` (both integers, immune to this)
    instead of trusting the `media` cell as-is."""
    hoja = _hoja_o_crear("pool_puntos", CABECERA_POOL_PUNTOS)
    hoja.clear()
    hoja.append_row(CABECERA_POOL_PUNTOS, value_input_option="USER_ENTERED")
    if filas:
        hoja.append_rows(filas, value_input_option="USER_ENTERED")


def leer_pool_puntos() -> list[dict]:
    try:
        return leer_hoja("pool_puntos")
    except gspread.WorksheetNotFound:
        return []


CABECERA_CHOLLOS_AVISADOS = ["fecha", "jugador", "posicion", "puntos_por_millon"]


def append_chollos_avisados(filas: list[list]) -> None:
    """Dedup for the Telegram bargain alert (aviso_chollos.py): a player is
    only ever alerted once — append-only, like puntos_jornada."""
    if not filas:
        return
    _hoja_o_crear("chollos_avisados", CABECERA_CHOLLOS_AVISADOS).append_rows(filas, value_input_option="USER_ENTERED")


def leer_chollos_avisados() -> list[dict]:
    try:
        return leer_hoja("chollos_avisados")
    except gspread.WorksheetNotFound:
        return []


def leer_config() -> dict:
    """The config tab is a single row of settings; returned as a plain dict."""
    filas = leer_hoja("config")
    return filas[0] if filas else {}
