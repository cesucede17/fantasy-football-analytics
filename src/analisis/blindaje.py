"""Release-clause risk and shield priority.

risk = (market_value - release_clause) * P(some rival has enough budget)

Rival budgets are inferred from the movimientos_liga tab. Check first that
the release-clause mechanic is active for this league (config).

While movimientos_liga has little history, the probability of a rival
having enough budget can't be estimated precisely per rival — a default
probability (explicitly flagged as such) is used based on the number of
participants, until real transfers are available to calibrate it.
"""
from __future__ import annotations

from dataclasses import dataclass

P_SALDO_INDIVIDUAL_POR_DEFECTO = 0.3


@dataclass
class RiesgoBlindaje:
    riesgo: float
    probabilidad_saldo: float
    estimacion_por_defecto: bool
    motivo: str


GASTOS = {"compra", "subida_clausula"}  # reduce available budget
INGRESOS = {"venta", "clausulazo"}  # increase available budget (clausulazo = collected by the rival)


def saldo_neto_por_manager(movimientos_liga: list[dict]) -> dict[str, float]:
    """Purchases and clause increases reduce budget; sales and collected
    release-clause payments increase it.

    Approximate: we don't know each rival's starting budget, only their
    observed net movement. Useful to compare rivals against each other, not
    as an absolute budget figure.
    """
    saldo: dict[str, float] = {}
    for mov in movimientos_liga:
        manager = mov.get("manager")
        if not manager:
            continue
        importe = float(mov.get("importe") or 0)
        tipo = str(mov.get("tipo", "")).lower()
        signo = -1 if tipo in GASTOS else 1
        saldo[manager] = saldo.get(manager, 0) + signo * importe
    return saldo


def calcular_riesgo_blindaje(
    valor_mercado: float,
    clausula: float,
    movimientos_liga: list[dict],
    n_participantes: int | None,
    clausulazo_activo: bool = True,
) -> RiesgoBlindaje:
    if not clausulazo_activo:
        return RiesgoBlindaje(0.0, 0.0, False, "Release-clause mechanic disabled for this league.")

    descuento = max(valor_mercado - clausula, 0)
    if descuento == 0:
        return RiesgoBlindaje(0.0, 0.0, False, "Clause at or above market value: no incentive to trigger it.")

    saldos = saldo_neto_por_manager(movimientos_liga)

    if saldos:
        rivales_con_saldo_ok = sum(1 for s in saldos.values() if s >= -descuento)
        prob = rivales_con_saldo_ok / len(saldos) if saldos else 0.0
        return RiesgoBlindaje(
            descuento * prob, prob, False,
            f"Estimated from {len(saldos)} rivals with recorded transfers.",
        )

    # No transfer history yet: default probability based on rival count.
    n = n_participantes or 1
    prob = 1 - (1 - P_SALDO_INDIVIDUAL_POR_DEFECTO) ** max(n - 1, 0)
    return RiesgoBlindaje(
        descuento * prob, prob, True,
        "No movimientos_liga history yet — default probability, not calibrated on real data.",
    )
