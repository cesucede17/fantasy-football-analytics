"""Contexto de enfrentamiento y estimación heurística de probabilidad de
victoria para decidir el once titular.

Aviso importante, para no perderlo de vista: esto es una heurística de
ponderación manual, NO un modelo estadístico validado. Se construye con
cero partidos observados de la temporada 2026/27 en el momento de escribir
esto — el usuario pidió explícitamente saltarse la regla de CLAUDE.md de
"nada de ML antes de fase 4" sabiendo que el número no está calibrado con
datos reales. Por eso `estimar_probabilidad_victoria` siempre devuelve el
desglose completo (`motivo`), no solo el porcentaje: el valor no es la
verdad, es un resumen legible de las señales que ya tenías dispersas.

Señales usadas, todas con datos reales (nada inventado salvo los pesos):
- Historial de enfrentamientos directos (últimos 5, en cualquier
  temporada — calendario_resultados no se filtra por año).
- Localía.
- Racha reciente de cada equipo (últimos 5 partidos, cualquier rival).
- Posición en la tabla: la de esta temporada si ya hay partidos jugados
  suficientes, si no la de la temporada anterior (clasificacion_anterior)
  como arranque — ver `tabla_posiciones`.
- Bajas: jugadores con lesión/sanción activa (estado_jugadores) que están
  entre los de más valor de mercado de su equipo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.textutil import normalizar

N_PARTIDOS_FORMA = 5
MIN_JORNADAS_PARA_TABLA_ACTUAL = 3  # por debajo de esto, se usa la tabla de la temporada anterior
N_BAJAS_IMPORTANTES = 3  # cuántos jugadores de más valor del rival se miran para lesiones/sanciones


def _eq(nombre: str) -> str:
    return normalizar(nombre)


def _int_o_none(valor) -> int | None:
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return int(float(texto))
    except ValueError:
        return None


def _partidos_jugados(calendario: list[dict]) -> list[dict]:
    return [p for p in calendario if str(p.get("jugado", "")).lower() == "si"]


def _orden_desc(partidos: list[dict]) -> list[dict]:
    """Más reciente primero. calendario_resultados no siempre tiene fecha
    (los partidos ya jugados solo traen jornada), así que se ordena por
    (temporada, jornada) en vez de por fecha real."""
    return sorted(partidos, key=lambda p: (str(p.get("temporada", "")), _int_o_none(p.get("jornada")) or 0), reverse=True)


def historial_h2h(equipo_a: str, equipo_b: str, calendario: list[dict], n: int = N_PARTIDOS_FORMA) -> list[dict]:
    """Últimos n enfrentamientos directos entre dos equipos, en cualquier
    temporada, más reciente primero."""
    a, b = _eq(equipo_a), _eq(equipo_b)
    jugados = _partidos_jugados(calendario)
    entre_ambos = [
        p for p in jugados
        if {_eq(p.get("equipo_local", "")), _eq(p.get("equipo_visitante", ""))} == {a, b}
    ]
    return _orden_desc(entre_ambos)[:n]


@dataclass
class ResumenH2H:
    partidos: list[dict]
    victorias_equipo_a: int
    empates: int
    victorias_equipo_b: int


def resumen_h2h(equipo_a: str, equipo_b: str, calendario: list[dict], n: int = N_PARTIDOS_FORMA) -> ResumenH2H:
    partidos = historial_h2h(equipo_a, equipo_b, calendario, n)
    a = _eq(equipo_a)
    v_a = v_b = empates = 0
    for p in partidos:
        gl, gv = _int_o_none(p.get("goles_local")), _int_o_none(p.get("goles_visitante"))
        if gl is None or gv is None:
            continue
        local_es_a = _eq(p.get("equipo_local", "")) == a
        goles_a, goles_b = (gl, gv) if local_es_a else (gv, gl)
        if goles_a > goles_b:
            v_a += 1
        elif goles_a < goles_b:
            v_b += 1
        else:
            empates += 1
    return ResumenH2H(partidos, v_a, empates, v_b)


def racha_reciente(equipo: str, calendario: list[dict], n: int = N_PARTIDOS_FORMA) -> str:
    """'VVEDV' (más reciente primero) con los últimos n partidos del
    equipo, cualquier rival. Solo mira la temporada más reciente en la que
    el equipo tiene partidos: el histórico de temporadas pasadas
    (backfill_historico_h2h) no trae jornada real, así que mezclarlo
    daría un orden arbitrario dentro de esa temporada — aquí interesa el
    orden real, no solo relleno. Al principio de temporada esto significa
    una racha más corta que n, no una inventada."""
    eq = _eq(equipo)
    jugados = [
        p for p in _partidos_jugados(calendario)
        if eq in (_eq(p.get("equipo_local", "")), _eq(p.get("equipo_visitante", "")))
    ]
    if not jugados:
        return ""
    temporada_reciente = max(str(p.get("temporada", "")) for p in jugados)
    jugados = [p for p in jugados if str(p.get("temporada", "")) == temporada_reciente]
    letras = []
    for p in _orden_desc(jugados)[:n]:
        gl, gv = _int_o_none(p.get("goles_local")), _int_o_none(p.get("goles_visitante"))
        if gl is None or gv is None:
            continue
        local_es_eq = _eq(p.get("equipo_local", "")) == eq
        goles_eq, goles_rival = (gl, gv) if local_es_eq else (gv, gl)
        letras.append("V" if goles_eq > goles_rival else "D" if goles_eq < goles_rival else "E")
    return "".join(letras)


def _puntos_racha(racha: str) -> int:
    return sum(3 if c == "V" else 1 if c == "E" else 0 for c in racha)


def proximo_partido(equipo: str, calendario: list[dict]) -> dict | None:
    """Primer partido sin jugar del equipo, por jornada ascendente."""
    eq = _eq(equipo)
    pendientes = [
        p for p in calendario
        if str(p.get("jugado", "")).lower() != "si"
        and eq in (_eq(p.get("equipo_local", "")), _eq(p.get("equipo_visitante", "")))
    ]
    if not pendientes:
        return None
    return sorted(pendientes, key=lambda p: _int_o_none(p.get("jornada")) or 0)[0]


def tabla_posiciones(calendario: list[dict], clasificacion_anterior: list[dict]) -> dict[str, int]:
    """Posición de cada equipo: la de esta temporada si ya se jugaron
    suficientes jornadas (>= MIN_JORNADAS_PARA_TABLA_ACTUAL), si no la de
    la temporada anterior como arranque. Un equipo recién ascendido que no
    esté en la tabla anterior no aparece — tratarlo como "sin dato", no
    como aviso de que juega mal."""
    jugados = _partidos_jugados(calendario)
    jornadas_jugadas = len({_int_o_none(p.get("jornada")) for p in jugados if p.get("jornada")})

    anterior = {p.get("equipo"): _int_o_none(p.get("posicion")) for p in clasificacion_anterior if p.get("equipo")}
    if jornadas_jugadas < MIN_JORNADAS_PARA_TABLA_ACTUAL:
        return {k: v for k, v in anterior.items() if v is not None}

    puntos: dict[str, int] = {}
    dif_goles: dict[str, int] = {}
    goles_favor: dict[str, int] = {}
    for p in jugados:
        gl, gv = _int_o_none(p.get("goles_local")), _int_o_none(p.get("goles_visitante"))
        if gl is None or gv is None:
            continue
        local, visitante = p.get("equipo_local", ""), p.get("equipo_visitante", "")
        for eq in (local, visitante):
            puntos.setdefault(eq, 0)
            dif_goles.setdefault(eq, 0)
            goles_favor.setdefault(eq, 0)
        if gl > gv:
            puntos[local] += 3
        elif gl < gv:
            puntos[visitante] += 3
        else:
            puntos[local] += 1
            puntos[visitante] += 1
        dif_goles[local] += gl - gv
        dif_goles[visitante] += gv - gl
        goles_favor[local] += gl
        goles_favor[visitante] += gv

    orden = sorted(puntos.keys(), key=lambda eq: (-puntos[eq], -dif_goles[eq], -goles_favor[eq]))
    return {eq: i + 1 for i, eq in enumerate(orden)}


def jugadores_lesionados_equipo(
    equipo: str, estado_jugadores: list[dict], precios_diarios: list[dict], n: int = N_BAJAS_IMPORTANTES
) -> list[str]:
    """Bajas activas (lesión o sanción) del equipo, priorizando a los de
    más valor de mercado — proxy de "jugador importante" sin tener que
    pedirle al usuario que lo marque a mano."""
    eq = _eq(equipo)
    equipo_por_jugador: dict[str, str] = {}
    valor_por_jugador: dict[str, int] = {}
    for fila in precios_diarios:
        nombre = fila.get("nombre")
        if not nombre:
            continue
        equipo_por_jugador[normalizar(nombre)] = fila.get("equipo", "")
        valor_actual = _int_o_none(fila.get("valor")) or 0
        clave = normalizar(nombre)
        if valor_actual > valor_por_jugador.get(clave, -1):
            valor_por_jugador[clave] = valor_actual

    # última incidencia conocida por jugador (estado_jugadores es append-only)
    ultima_por_jugador: dict[str, dict] = {}
    for inc in estado_jugadores:
        jugador = inc.get("jugador")
        if not jugador:
            continue
        clave = normalizar(jugador)
        anterior = ultima_por_jugador.get(clave)
        if anterior is None or str(inc.get("fecha", "")) >= str(anterior.get("fecha", "")):
            ultima_por_jugador[clave] = inc

    del_equipo = [
        (nombre, valor_por_jugador.get(nombre, 0), inc.get("jugador"))
        for nombre, inc in ultima_por_jugador.items()
        if equipo_por_jugador.get(nombre) and _eq(equipo_por_jugador[nombre]) == eq
    ]
    del_equipo.sort(key=lambda t: t[1], reverse=True)
    return [nombre_original for _, _, nombre_original in del_equipo[:n]]


@dataclass
class ResultadoProbabilidad:
    """`motivo` lleva el desglose completo — no es solo el % final, porque
    el % es una estimación heurística sin calibrar, ver docstring del
    módulo. Enseñar el porqué es lo que hace que el usuario pueda
    descartar la estimación si no le cuadra con lo que sabe."""
    prob_victoria_local: float
    prob_empate: float
    prob_victoria_visitante: float
    motivo: list[str] = field(default_factory=list)


def estimar_probabilidad_victoria(
    equipo_local: str,
    equipo_visitante: str,
    calendario: list[dict],
    clasificacion_anterior: list[dict],
    estado_jugadores: list[dict],
    precios_diarios: list[dict],
) -> ResultadoProbabilidad:
    """Estimación heurística (no ML, no calibrada) de quién gana. Parte de
    una base realista de fútbol (ventaja de local) y la desplaza según
    enfrentamientos directos, racha, posición en la tabla y bajas — cada
    señal con un tope máximo de influencia para que ninguna por sí sola
    dispare el resultado a un extremo."""
    motivo: list[str] = []
    base_local, base_empate, base_visitante = 45.0, 26.0, 29.0
    desplazamiento = 0.0  # positivo = a favor del local

    h2h = resumen_h2h(equipo_local, equipo_visitante, calendario)
    n_h2h = h2h.victorias_equipo_a + h2h.empates + h2h.victorias_equipo_b
    if n_h2h:
        ajuste_h2h = 15.0 * (h2h.victorias_equipo_a - h2h.victorias_equipo_b) / N_PARTIDOS_FORMA
        desplazamiento += ajuste_h2h
        motivo.append(
            f"H2H últimos {n_h2h}: {h2h.victorias_equipo_a}V {h2h.empates}E {h2h.victorias_equipo_b}D "
            f"a favor de {equipo_local} → {ajuste_h2h:+.1f} pts"
        )
    else:
        motivo.append("Sin enfrentamientos directos registrados todavía → sin ajuste por H2H.")

    racha_local = racha_reciente(equipo_local, calendario)
    racha_visitante = racha_reciente(equipo_visitante, calendario)
    if racha_local or racha_visitante:
        diferencia_forma = _puntos_racha(racha_local) - _puntos_racha(racha_visitante)
        ajuste_forma = 10.0 * diferencia_forma / 15.0
        desplazamiento += ajuste_forma
        motivo.append(
            f"Racha: {equipo_local} {racha_local or 's/d'} vs {equipo_visitante} {racha_visitante or 's/d'} "
            f"→ {ajuste_forma:+.1f} pts"
        )

    tabla = tabla_posiciones(calendario, clasificacion_anterior)
    pos_local, pos_visitante = tabla.get(equipo_local), tabla.get(equipo_visitante)
    if pos_local is not None and pos_visitante is not None:
        ajuste_tabla = 10.0 * (pos_visitante - pos_local) / 19.0
        desplazamiento += ajuste_tabla
        motivo.append(f"Tabla: {equipo_local} {pos_local}º vs {equipo_visitante} {pos_visitante}º → {ajuste_tabla:+.1f} pts")
    else:
        motivo.append("Posición en tabla no disponible para uno de los dos equipos → sin ajuste.")

    bajas_local = jugadores_lesionados_equipo(equipo_local, estado_jugadores, precios_diarios)
    bajas_visitante = jugadores_lesionados_equipo(equipo_visitante, estado_jugadores, precios_diarios)
    ajuste_bajas = -2.5 * len(bajas_local) + 2.5 * len(bajas_visitante)
    if bajas_local or bajas_visitante:
        desplazamiento += ajuste_bajas
        detalle_local = ", ".join(bajas_local) if bajas_local else "ninguna detectada"
        detalle_visitante = ", ".join(bajas_visitante) if bajas_visitante else "ninguna detectada"
        motivo.append(
            f"Bajas de más valor — {equipo_local}: {detalle_local} · {equipo_visitante}: {detalle_visitante} "
            f"→ {ajuste_bajas:+.1f} pts"
        )

    desplazamiento = max(-35.0, min(35.0, desplazamiento))
    local = max(5.0, min(85.0, base_local + desplazamiento))
    visitante = max(5.0, min(85.0, base_visitante - desplazamiento))
    empate = max(100.0 - local - visitante, 5.0)
    total = local + empate + visitante
    local, empate, visitante = 100 * local / total, 100 * empate / total, 100 * visitante / total

    motivo.insert(0, f"Base de partida (ventaja de local, sin más datos): {base_local:.0f}%/{base_empate:.0f}%/{base_visitante:.0f}%.")
    return ResultadoProbabilidad(round(local, 1), round(empate, 1), round(visitante, 1), motivo)
