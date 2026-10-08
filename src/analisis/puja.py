"""Precio óptimo de puja.

Subasta a sobre cerrado a primer precio: se puja contra los rivales, no contra
el valor de mercado. Variable objetivo: sobreprecio = puja_ganadora / valor - 1.

Fases 2-3: heurística (escasez posicional, forma reciente, exposición en webs).
Fase 4: regresión, solo con 40+ pujas reales registradas.
Devolver siempre un intervalo, no un número.

Sin pujas reales registradas todavía (`movimientos_liga` con tipo=compra
observado), el intervalo es deliberadamente ancho y centrado en valores
conservadores de mercado. Se irá estrechando en Fase 4.
"""
from __future__ import annotations

from dataclasses import dataclass

SOBREPRECIO_BASE_MIN = 0.05
SOBREPRECIO_BASE_MAX = 0.20


@dataclass
class EstimacionPuja:
    sobreprecio_min: float
    sobreprecio_max: float
    puja_sugerida_min: float
    puja_sugerida_max: float
    motivo: str


def _factor_escasez(posicion: str, jugadores_pool: list[dict]) -> float:
    """Cuanto menor la proporción de jugadores de esa posición en el pool
    de relevantes, más escaso el puesto y mayor el sobreprecio esperado."""
    if not jugadores_pool:
        return 1.0
    total = len(jugadores_pool)
    misma_posicion = sum(1 for j in jugadores_pool if j.get("posicion") == posicion)
    if misma_posicion == 0:
        return 1.0
    proporcion = misma_posicion / total
    # proporción típica de porteros ~0.15-0.2; a menor proporción, mayor factor.
    return max(0.15 / proporcion, 0.7) if proporcion > 0 else 1.3


def _factor_forma(delta_7d: int | None, valor_mercado: float) -> float:
    if not delta_7d or valor_mercado <= 0:
        return 1.0
    variacion_relativa = delta_7d / valor_mercado
    # +10% en 7 días añade hasta +0.3 al factor; a la baja resta hasta -0.2.
    return 1.0 + max(min(variacion_relativa * 3, 0.3), -0.2)


def estimar_sobreprecio(
    valor_mercado: float,
    posicion: str,
    delta_7d: int | None,
    jugadores_pool: list[dict],
) -> EstimacionPuja:
    factor = _factor_escasez(posicion, jugadores_pool) * _factor_forma(delta_7d, valor_mercado)

    sobreprecio_min = SOBREPRECIO_BASE_MIN * factor
    sobreprecio_max = SOBREPRECIO_BASE_MAX * factor

    return EstimacionPuja(
        sobreprecio_min=sobreprecio_min,
        sobreprecio_max=sobreprecio_max,
        puja_sugerida_min=valor_mercado * (1 + sobreprecio_min),
        puja_sugerida_max=valor_mercado * (1 + sobreprecio_max),
        motivo=(
            "Heurística por escasez posicional y forma reciente — "
            "sin pujas reales registradas aún (hacen falta 40+ para pasar a "
            "un modelo ajustado, Fase 4)."
        ),
    )
