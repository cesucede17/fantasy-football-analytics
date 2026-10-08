"""Daily 100,000€ bonus the game gives for watching an ad.

Only the user and their rival "Luis" get it — the other managers don't
receive it (or haven't said so, so it isn't assumed). Logged as just
another entry in movimientos_liga (type "bono", no associated player), so
it flows straight into everyone's dinero_actual calculation.
"""
from __future__ import annotations

import datetime as dt

MANAGERS_CON_BONO = ["Yo", "Luis"]
IMPORTE_BONO = 100000


def main() -> None:
    from src.alertas.telegram import notificar_fallo
    from src.storage.sheets import agregar_movimiento_liga

    try:
        hoy = dt.date.today().isoformat()
        for manager in MANAGERS_CON_BONO:
            agregar_movimiento_liga(hoy, "", "bono", manager, IMPORTE_BONO)
        print(f"OK: daily bonus added for {', '.join(MANAGERS_CON_BONO)}.")
    except Exception as err:
        notificar_fallo("bono_diario", err)
        raise


if __name__ == "__main__":
    main()
