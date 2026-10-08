"""Lectura y escritura en Google Sheets vía gspread.

precios_diarios es append-only: nunca sobrescribir filas.

Autenticación: cuenta de servicio de Google Cloud. Las credenciales llegan
como JSON (contenido completo, no ruta de archivo) en la variable de entorno
GOOGLE_CREDENTIALS_JSON — así funciona igual en local (.env) y en GitHub
Actions (secret). La hoja debe compartirse con el email de esa cuenta de
servicio (termina en @...iam.gserviceaccount.com) con permiso de Editor.
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
            "Falta GOOGLE_CREDENTIALS_JSON (contenido del JSON de la cuenta "
            "de servicio, no una ruta de archivo)."
        )
    info = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _hoja(nombre_pestana: str):
    if not GOOGLE_SHEET_ID:
        raise RuntimeError("Falta GOOGLE_SHEET_ID.")
    return _cliente().open_by_key(GOOGLE_SHEET_ID).worksheet(nombre_pestana)


def _hoja_o_crear(nombre_pestana: str, cabecera: list[str]):
    """Como _hoja, pero crea la pestaña con su cabecera si todavía no
    existe — para no obligar a crearla a mano en el Sheet."""
    if not GOOGLE_SHEET_ID:
        raise RuntimeError("Falta GOOGLE_SHEET_ID.")
    libro = _cliente().open_by_key(GOOGLE_SHEET_ID)
    try:
        return libro.worksheet(nombre_pestana)
    except gspread.WorksheetNotFound:
        hoja = libro.add_worksheet(title=nombre_pestana, rows=1000, cols=max(len(cabecera), 1))
        hoja.append_row(cabecera, value_input_option="USER_ENTERED")
        return hoja


def append_precios_diarios(filas: list[list]) -> None:
    """Añade filas a `precios_diarios`. Nunca hace update ni overwrite."""
    if not filas:
        return
    _hoja("precios_diarios").append_rows(filas, value_input_option="USER_ENTERED")


def append_estado_jugadores(filas: list[list]) -> None:
    """Añade filas a `estado_jugadores` (lesiones/sanciones). Append-only."""
    if not filas:
        return
    _hoja("estado_jugadores").append_rows(filas, value_input_option="USER_ENTERED")


def sobrescribir_estado_forma(filas: list[list]) -> None:
    """Reemplaza por completo `estado_forma`: es una foto del estado actual
    de los jugadores seguidos, no un histórico — a diferencia de las pestañas
    append-only, aquí interesa solo el dato más reciente."""
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
    """Marca qué jugadores de mi_plantilla son titulares en la alineación
    actual. El resto queda como banquillo. Se guarda en una columna
    `titular`, añadida a la pestaña la primera vez que se usa esto."""
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
    valores = hoja.col_values(1)  # columna "jugador"
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
    """Vacía mercado_diario entero, conservando la cabecera. El mercado real
    de LaLiga Fantasy rota cada día a las 22:00 — sin esto, los jugadores de
    mercados ya cerrados se quedarían acumulados."""
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
    """Lee una pestaña entera como lista de diccionarios (fila 1 = cabeceras)."""
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
    """Añade filas a `puntos_jornada`. Append-only, como precios_diarios:
    cada jornada jugada es un hecho histórico que no cambia. El scraper
    (scraper_perfil) es responsable de no volver a mandar una jornada ya
    guardada para ese jugador — aquí no se hace dedup."""
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
    """Reemplaza por completo `calendario_resultados`: cada pasada trae el
    calendario entero (jugados y por jugar), así que no tiene sentido
    acumular — solo interesa la foto más reciente, con los resultados que
    se van cerrando."""
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
    """Clasificación final de la temporada pasada. Dato estático de
    referencia (no se re-scrapea): sirve de punto de partida al inicio de
    temporada, cuando todavía no hay partidos jugados con los que calcular
    una clasificación real."""
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
    """Puntos de LaLiga Fantasy Oficial del pool entero (scraper_puntos_pool),
    base para el scouting de chollos. Foto del estado actual, no histórico
    (a diferencia de puntos_jornada): cada pasada sobrescribe la pestaña
    entera, igual que estado_forma.

    OJO al leer `media` de vuelta con leer_pool_puntos()/leer_hoja(): esta
    hoja se escribe bien (Sheets guarda 4.33 de verdad), pero gspread lee
    con get_all_records() en modo FORMATTED_VALUE + numericise propio, que
    NO entiende el separador decimal español ("4,33" tal como lo muestra
    la celda) — lo interpreta como millares y devuelve 433. Comprobado a
    mano en la sesión donde se creó esto (ver docs/04-bitacora.md). No
    afecta a la web (Apps Script lee con getValues(), sin este problema) ni
    a nada que exista hoy en Python (nada lee `media` todavía). Si algún
    día hace falta desde Python, recalcular como
    `puntos_temporada / partidos_jugados` (ambos enteros, inmunes a esto)
    en vez de confiar en la celda `media` tal cual."""
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
    """Dedup del aviso de chollos por Telegram (aviso_chollos.py): un
    jugador solo se avisa una vez, para siempre — append-only, como
    puntos_jornada."""
    if not filas:
        return
    _hoja_o_crear("chollos_avisados", CABECERA_CHOLLOS_AVISADOS).append_rows(filas, value_input_option="USER_ENTERED")


def leer_chollos_avisados() -> list[dict]:
    try:
        return leer_hoja("chollos_avisados")
    except gspread.WorksheetNotFound:
        return []


def leer_config() -> dict:
    """La pestaña config es una sola fila de ajustes; se devuelve como dict plano."""
    filas = leer_hoja("config")
    return filas[0] if filas else {}
