"""Optimal bid price.

Sealed first-price auction: you bid against your rivals, not against the
market value. Target variable: overpay = winning_bid / value - 1.

Phases 2-3: heuristic (positional scarcity, recent form, exposure on public
sites). Phase 4: regression, only once 40+ real bids are logged.
Always return a range, never a single number.

With no real bids logged yet (`movimientos_liga` with type=purchase
observed), the range is deliberately wide and centered on conservative
market values. It narrows in Phase 4.
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
    """The lower a position's share within the relevant player pool, the
    scarcer that slot and the higher the expected overpay."""
    if not jugadores_pool:
        return 1.0
    total = len(jugadores_pool)
    misma_posicion = sum(1 for j in jugadores_pool if j.get("posicion") == posicion)
    if misma_posicion == 0:
        return 1.0
    proporcion = misma_posicion / total
    # typical goalkeeper share ~0.15-0.2; the lower the share, the higher the factor.
    return max(0.15 / proporcion, 0.7) if proporcion > 0 else 1.3


def _factor_forma(delta_7d: int | None, valor_mercado: float) -> float:
    if not delta_7d or valor_mercado <= 0:
        return 1.0
    variacion_relativa = delta_7d / valor_mercado
    # +10% over 7 days adds up to +0.3 to the factor; a drop subtracts up to -0.2.
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
            "Heuristic based on positional scarcity and recent form — "
            "no real bids logged yet (40+ needed before switching to a "
            "fitted model, Phase 4)."
        ),
    )
