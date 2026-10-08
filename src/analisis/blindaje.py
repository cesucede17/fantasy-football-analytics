"""Riesgo de clausulazo y prioridad de blindaje.

riesgo = (valor_mercado - clausula) * P(algún rival tenga saldo suficiente)

El saldo de los rivales se infiere de la pestaña movimientos_liga. Comprobar
antes que el clausulazo esté activo en la liga (config).

Mientras `movimientos_liga` tenga poco histórico, la probabilidad de saldo no
se puede estimar con precisión por rival — se usa una probabilidad por
defecto (marcada como tal) en función del número de participantes, hasta que
haya movimientos reales que ajustarla.
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


GASTOS = {"compra", "subida_clausula"}  # restan saldo
INGRESOS = {"venta", "clausulazo"}  # suman saldo (clausulazo = cobrado por el rival)


def saldo_neto_por_manager(movimientos_liga: list[dict]) -> dict[str, float]:
    """Compras y subidas de cláusula restan saldo; ventas y clausulazos
    cobrados suman.

    Aproximado: no conocemos el saldo inicial de cada rival, solo su
    movimiento neto observado. Sirve para comparar rivales entre sí, no
    como saldo absoluto.
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
        return RiesgoBlindaje(0.0, 0.0, False, "Clausulazo desactivado en esta liga.")

    descuento = max(valor_mercado - clausula, 0)
    if descuento == 0:
        return RiesgoBlindaje(0.0, 0.0, False, "Cláusula igual o por encima del valor de mercado: sin incentivo.")

    saldos = saldo_neto_por_manager(movimientos_liga)

    if saldos:
        rivales_con_saldo_ok = sum(1 for s in saldos.values() if s >= -descuento)
        prob = rivales_con_saldo_ok / len(saldos) if saldos else 0.0
        return RiesgoBlindaje(
            descuento * prob, prob, False,
            f"Estimado a partir de {len(saldos)} rivales con movimientos registrados.",
        )

    # Sin histórico de movimientos: probabilidad por defecto según nº de rivales.
    n = n_participantes or 1
    prob = 1 - (1 - P_SALDO_INDIVIDUAL_POR_DEFECTO) ** max(n - 1, 0)
    return RiesgoBlindaje(
        descuento * prob, prob, True,
        "Sin movimientos_liga todavía — probabilidad por defecto, no ajustada a datos reales.",
    )
