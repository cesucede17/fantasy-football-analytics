"""Vacía `mercado_diario` cada día a las 22:00 (hora de Madrid), que es
cuando LaLiga Fantasy abre un mercado nuevo. Sin esto, los jugadores de
mercados ya cerrados se irían acumulando en la pestaña.
"""
from __future__ import annotations


def main() -> None:
    from src.alertas.telegram import notificar_fallo
    from src.storage.sheets import resetear_mercado_diario

    try:
        resetear_mercado_diario()
    except Exception as err:
        notificar_fallo("resetear_mercado", err)
        raise


if __name__ == "__main__":
    main()
