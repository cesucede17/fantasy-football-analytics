"""Bono diario de 100.000€ que da el juego por ver un anuncio.

Solo lo ven el usuario y su rival "Luis" — el resto de managers no lo
reciben (o no lo ha dicho, así que no se asume). Se registra como un
movimiento más en movimientos_liga (tipo "bono", sin jugador asociado),
así entra solo en el cálculo de dinero_actual de cada uno.
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
        print(f"OK: bono diario añadido para {', '.join(MANAGERS_CON_BONO)}.")
    except Exception as err:
        notificar_fallo("bono_diario", err)
        raise


if __name__ == "__main__":
    main()
