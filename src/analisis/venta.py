"""Sell decision.

Sell when the expected price trend over 3-5 days is negative, not when the
asset is simply expensive. Expensive and still rising means hold.

`precios_diarios` already comes with delta_1d and delta_7d computed by the
source (futbolfantasy), so no need to accumulate several days of local
history for a first trend estimate — delta_7d/7 is used as the expected
daily derivative, with delta_1d as an early signal of acceleration.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DecisionVenta:
    decision: str  # "sell" | "hold" | "insufficient_data"
    derivada_diaria: float | None
    motivo: str


def evaluar_venta(delta_1d: int | None, delta_7d: int | None) -> DecisionVenta:
    if delta_7d is None:
        return DecisionVenta("insufficient_data", None, "No delta_7d available.")

    derivada = delta_7d / 7

    if derivada >= 0:
        return DecisionVenta(
            "hold", derivada,
            "Flat or rising weekly trend — expensive and still rising means hold.",
        )

    # Downward trend. If the last day already shows the drop slowing, give it margin.
    if delta_1d is not None and delta_1d >= 0:
        return DecisionVenta(
            "hold", derivada,
            "Weekly drop, but the last day is no longer falling — watch one more day before selling.",
        )

    return DecisionVenta(
        "sell", derivada,
        f"Negative trend (~{derivada:,.0f}/day) with no sign of slowing.",
    )
