"""Empties `mercado_diario` every day at 22:00 (Madrid time), which is when
LaLiga Fantasy opens a new market. Without this, players from markets
already closed would keep piling up in the tab.
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
