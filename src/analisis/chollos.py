"""Scouting de chollos externos — misma lógica y mismos umbrales que
web/js/paginas/chollos.js (no es un puerto automático: si cambia la
fórmula ahí, replicar el cambio aquí a mano). Existe por separado para
poder avisar por Telegram sin depender de que el usuario abra la web. Ver
docs/04-bitacora.md, paso 4 del brainstorming de decisión, para el porqué
de la fuente (pool_puntos vía futbolfantasy.com, no Comuniate/Analítica
Fantasy — puntúan Comunio/Biwenger, no LaLiga Fantasy Oficial).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

MIN_PUNTOS = 4  # con menos, un jugador barato parece "eficientísimo" solo por muestra mínima
TOP_POR_POSICION = 3  # igual que el panel "Refuerzos recomendados por posición" de la web
ORDEN_LINEAS = ["Portero", "Defensa", "Mediocampista", "Delantero"]


def normalizar(texto: str) -> str:
    t = (texto or "").strip().lower()
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


@dataclass
class Candidato:
    jugador: str
    equipo: str
    posicion: str
    puntos: int
    valor: float
    puntos_por_millon: float


def _valor_actual(nombre: str, snapshot: list[dict]) -> float | None:
    objetivo = normalizar(nombre)
    for fila in snapshot:
        candidato = normalizar(fila.get("nombre", ""))
        if objetivo in candidato or candidato in objetivo:
            try:
                return float(fila.get("valor") or 0) or None
            except (TypeError, ValueError):
                return None
    return None


def _con_puntos_por_millon(fila: dict, snapshot: list[dict]) -> Candidato | None:
    valor = _valor_actual(fila.get("jugador", ""), snapshot)
    if not valor or valor <= 0:
        return None
    try:
        puntos = int(float(fila.get("puntos_temporada") or 0))
    except (TypeError, ValueError):
        puntos = 0
    return Candidato(
        jugador=fila.get("jugador", ""),
        equipo=fila.get("equipo", ""),
        posicion=fila.get("posicion", ""),
        puntos=puntos,
        valor=valor,
        puntos_por_millon=puntos / (valor / 1_000_000),
    )


def top_refuerzos_por_posicion(pool_puntos: list[dict], snapshot: list[dict], mi_plantilla: list[dict]) -> list[Candidato]:
    """Los TOP_POR_POSICION candidatos externos por línea que mejoran al
    peor jugador propio de esa línea — exactamente lo que ya muestra
    "Refuerzos recomendados por posición" en la web, aquí en Python para
    poder avisar por Telegram."""
    nombres_propios = {normalizar(j.get("jugador", "")) for j in mi_plantilla}

    candidatos = []
    for fila in pool_puntos:
        if normalizar(fila.get("jugador", "")) in nombres_propios:
            continue
        c = _con_puntos_por_millon(fila, snapshot)
        if c and c.puntos >= MIN_PUNTOS:
            candidatos.append(c)

    mis_jugadores = []
    for j in mi_plantilla:
        nombre_obj = normalizar(j.get("jugador", ""))
        fila_pool = next((f for f in pool_puntos if normalizar(f.get("jugador", "")) == nombre_obj), None)
        if fila_pool:
            c = _con_puntos_por_millon(fila_pool, snapshot)
            if c:
                mis_jugadores.append(c)

    top = []
    for posicion in ORDEN_LINEAS:
        mios_pos = [c for c in mis_jugadores if c.posicion == posicion]
        peor = min(mios_pos, key=lambda c: c.puntos_por_millon) if mios_pos else None

        candidatos_pos = [
            c for c in candidatos
            if c.posicion == posicion and (peor is None or c.puntos_por_millon > peor.puntos_por_millon)
        ]
        candidatos_pos.sort(key=lambda c: c.puntos_por_millon, reverse=True)
        top.extend(candidatos_pos[:TOP_POR_POSICION])

    return top
