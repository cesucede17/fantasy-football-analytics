"""Decisión de venta.

Se vende cuando la derivada esperada de precio a 3-5 días es negativa,
no cuando el jugador está caro. Caro y subiendo se mantiene.

`precios_diarios` ya trae delta_1d y delta_7d calculados por la fuente
(futbolfantasy), así que no hace falta acumular varios días de histórico
propio para tener una primera estimación de tendencia — se usa delta_7d/7
como derivada diaria esperada, con delta_1d como aviso de aceleración.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DecisionVenta:
    decision: str  # "vender" | "mantener" | "datos_insuficientes"
    derivada_diaria: float | None
    motivo: str


def evaluar_venta(delta_1d: int | None, delta_7d: int | None) -> DecisionVenta:
    if delta_7d is None:
        return DecisionVenta("datos_insuficientes", None, "Sin delta_7d disponible.")

    derivada = delta_7d / 7

    if derivada >= 0:
        return DecisionVenta(
            "mantener", derivada,
            "Tendencia semanal plana o al alza — caro y subiendo se mantiene.",
        )

    # Tendencia bajista. Si el último día ya frena la caída, dar margen.
    if delta_1d is not None and delta_1d >= 0:
        return DecisionVenta(
            "mantener", derivada,
            "Bajada semanal, pero el último día ya no cae — vigilar un día más antes de vender.",
        )

    return DecisionVenta(
        "vender", derivada,
        f"Derivada negativa (~{derivada:,.0f}/día) sin señal de frenada.",
    )
