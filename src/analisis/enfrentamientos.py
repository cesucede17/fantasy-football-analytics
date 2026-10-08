"""Matchup context and heuristic win-probability estimate for lineup
decisions.

Important disclaimer, not to be lost sight of: this is a manually-weighted
heuristic, NOT a validated statistical model. It's built with zero observed
matches of the 2026/27 season at the time of writing — the user explicitly
asked to skip the project's "no ML before Phase 4" rule knowing the number
isn't calibrated against real data. That's why `estimar_probabilidad_victoria`
always returns the full breakdown (`motivo`), not just the percentage: the
value isn't ground truth, it's a readable summary of signals you already had
scattered around.

Signals used, all backed by real data (nothing invented except the weights):
- Head-to-head history (last 5, across any season — calendario_resultados
  isn't filtered by year).
- Home advantage.
- Each team's recent form (last 5 matches, any opponent).
- League position: this season's if enough matches have been played, else
  last season's (clasificacion_anterior) as a starting point — see
  `tabla_posiciones`.
- Absences: players with an active injury/suspension (estado_jugadores)
  who rank among their team's highest market value.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.textutil import normalizar

N_PARTIDOS_FORMA = 5
MIN_JORNADAS_PARA_TABLA_ACTUAL = 3  # below this, fall back to last season's table
N_BAJAS_IMPORTANTES = 3  # how many of the rival's highest-value players are checked for injuries/suspensions


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
    """Most recent first. calendario_resultados doesn't always have a date
    (matches already played only carry a matchday number), so it's sorted
    by (season, matchday) instead of a real date."""
    return sorted(partidos, key=lambda p: (str(p.get("temporada", "")), _int_o_none(p.get("jornada")) or 0), reverse=True)


def historial_h2h(equipo_a: str, equipo_b: str, calendario: list[dict], n: int = N_PARTIDOS_FORMA) -> list[dict]:
    """Last n head-to-head matches between two teams, across any season,
    most recent first."""
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
    """'WWDLW' (most recent first) for the team's last n matches, any
    opponent. Only looks at the most recent season the team has matches in:
    the historical backfill from past seasons (backfill_historico_h2h)
    doesn't carry a real matchday number, so mixing it in would give an
    arbitrary order within that season — here the real order matters, not
    just padding the count. Early in a season this means a shorter streak
    than n, not a made-up one."""
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
        letras.append("W" if goles_eq > goles_rival else "L" if goles_eq < goles_rival else "D")
    return "".join(letras)


def _puntos_racha(racha: str) -> int:
    return sum(3 if c == "W" else 1 if c == "D" else 0 for c in racha)


def proximo_partido(equipo: str, calendario: list[dict]) -> dict | None:
    """Team's first unplayed match, by ascending matchday."""
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
    """Each team's position: this season's once enough matchdays have been
    played (>= MIN_JORNADAS_PARA_TABLA_ACTUAL), else last season's as a
    starting point. A newly promoted team absent from last season's table
    simply doesn't appear — treat that as "no data", not as a signal that
    it's playing badly."""
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
    """Active absences (injury or suspension) for the team, prioritizing
    the highest market-value players — a proxy for "important player"
    without needing the user to flag it by hand."""
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

    # latest known incident per player (estado_jugadores is append-only)
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
    """`motivo` carries the full breakdown — not just the final %, because
    the % is an uncalibrated heuristic estimate (see the module docstring).
    Showing the reasoning is what lets the user discard the estimate when
    it doesn't match what they already know."""
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
    """Heuristic (not ML, not calibrated) estimate of who wins. Starts from
    a realistic football baseline (home advantage) and shifts it based on
    head-to-head record, recent form, league position, and absences — each
    signal capped so no single one alone can push the result to an
    extreme."""
    motivo: list[str] = []
    base_local, base_empate, base_visitante = 45.0, 26.0, 29.0
    desplazamiento = 0.0  # positive = favors the home team

    h2h = resumen_h2h(equipo_local, equipo_visitante, calendario)
    n_h2h = h2h.victorias_equipo_a + h2h.empates + h2h.victorias_equipo_b
    if n_h2h:
        ajuste_h2h = 15.0 * (h2h.victorias_equipo_a - h2h.victorias_equipo_b) / N_PARTIDOS_FORMA
        desplazamiento += ajuste_h2h
        motivo.append(
            f"H2H last {n_h2h}: {h2h.victorias_equipo_a}W {h2h.empates}D {h2h.victorias_equipo_b}L "
            f"in favor of {equipo_local} → {ajuste_h2h:+.1f} pts"
        )
    else:
        motivo.append("No head-to-head matches recorded yet → no H2H adjustment.")

    racha_local = racha_reciente(equipo_local, calendario)
    racha_visitante = racha_reciente(equipo_visitante, calendario)
    if racha_local or racha_visitante:
        diferencia_forma = _puntos_racha(racha_local) - _puntos_racha(racha_visitante)
        ajuste_forma = 10.0 * diferencia_forma / 15.0
        desplazamiento += ajuste_forma
        motivo.append(
            f"Form: {equipo_local} {racha_local or 'n/a'} vs {equipo_visitante} {racha_visitante or 'n/a'} "
            f"→ {ajuste_forma:+.1f} pts"
        )

    tabla = tabla_posiciones(calendario, clasificacion_anterior)
    pos_local, pos_visitante = tabla.get(equipo_local), tabla.get(equipo_visitante)
    if pos_local is not None and pos_visitante is not None:
        ajuste_tabla = 10.0 * (pos_visitante - pos_local) / 19.0
        desplazamiento += ajuste_tabla
        motivo.append(f"Table: {equipo_local} {pos_local}th vs {equipo_visitante} {pos_visitante}th → {ajuste_tabla:+.1f} pts")
    else:
        motivo.append("League position unavailable for one of the two teams → no adjustment.")

    bajas_local = jugadores_lesionados_equipo(equipo_local, estado_jugadores, precios_diarios)
    bajas_visitante = jugadores_lesionados_equipo(equipo_visitante, estado_jugadores, precios_diarios)
    ajuste_bajas = -2.5 * len(bajas_local) + 2.5 * len(bajas_visitante)
    if bajas_local or bajas_visitante:
        desplazamiento += ajuste_bajas
        detalle_local = ", ".join(bajas_local) if bajas_local else "none detected"
        detalle_visitante = ", ".join(bajas_visitante) if bajas_visitante else "none detected"
        motivo.append(
            f"Highest-value absences — {equipo_local}: {detalle_local} · {equipo_visitante}: {detalle_visitante} "
            f"→ {ajuste_bajas:+.1f} pts"
        )

    desplazamiento = max(-35.0, min(35.0, desplazamiento))
    local = max(5.0, min(85.0, base_local + desplazamiento))
    visitante = max(5.0, min(85.0, base_visitante - desplazamiento))
    empate = max(100.0 - local - visitante, 5.0)
    total = local + empate + visitante
    local, empate, visitante = 100 * local / total, 100 * empate / total, 100 * visitante / total

    motivo.insert(0, f"Starting baseline (home advantage, no other data): {base_local:.0f}%/{base_empate:.0f}%/{base_visitante:.0f}%.")
    return ResultadoProbabilidad(round(local, 1), round(empate, 1), round(visitante, 1), motivo)
