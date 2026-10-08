"""Alerts via Telegram about new bargains that would reinforce some squad
position — same criteria as "Recommended reinforcements by position" in the
web dashboard's Chollos tab (decision brainstorm step 4, see
docs/04-bitacora.md). Explicit user request: didn't want to have to open
the web dashboard just to find out.

Depends on `pool_puntos` already being updated for today — runs AFTER
scraper_puntos_pool in the daily cron (see ingesta-diaria.yml).

Each player is alerted at most once, ever (dedup via chollos_avisados,
append-only) — without this, as the market's prices drop or points rise,
the same top-3-per-position would repeat every day.
"""
from __future__ import annotations

import datetime as dt


def main() -> None:
    from src.alertas.telegram import enviar_mensaje, notificar_fallo
    from src.analisis.chollos import normalizar, top_refuerzos_por_posicion
    from src.storage.sheets import (
        append_chollos_avisados,
        leer_chollos_avisados,
        leer_hoja,
        leer_mi_plantilla,
        leer_pool_puntos,
    )

    try:
        pool = leer_pool_puntos()
        if not pool:
            print("OK: pool_puntos still empty, nothing to alert.")
            return

        precios = leer_hoja("precios_diarios")
        if not precios:
            print("OK: precios_diarios still empty, nothing to alert.")
            return
        fecha_max = max(f.get("fecha", "") for f in precios)
        snapshot = [f for f in precios if f.get("fecha") == fecha_max]

        mi_plantilla = leer_mi_plantilla()
        top = top_refuerzos_por_posicion(pool, snapshot, mi_plantilla)

        ya_avisados = {normalizar(f.get("jugador", "")) for f in leer_chollos_avisados()}
        nuevos = [c for c in top if normalizar(c.jugador) not in ya_avisados]

        if not nuevos:
            print("OK: no new bargains today.")
            return

        lineas = [
            f"💎 {c.jugador} ({c.equipo}, {c.posicion}) — {c.puntos_por_millon:.1f} pts/M€, "
            f"{c.puntos} points, {c.valor:,.0f}€".replace(",", ".")
            for c in nuevos
        ]
        enviar_mensaje("🔎 New bargains that could reinforce your squad:\n\n" + "\n".join(lineas))

        hoy = dt.date.today().isoformat()
        append_chollos_avisados([[hoy, c.jugador, c.posicion, round(c.puntos_por_millon, 2)] for c in nuevos])
        print(f"OK: alerted {len(nuevos)} new bargains.")
    except Exception as err:
        notificar_fallo("aviso_chollos", err)
        raise


if __name__ == "__main__":
    main()
