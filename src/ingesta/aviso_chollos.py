"""Avisa por Telegram de chollos nuevos que refuercen alguna posición de la
plantilla — mismo criterio que "Refuerzos recomendados por posición" en la
pestaña Chollos de la web (paso 4 del brainstorming, ver
docs/04-bitacora.md). Pedido explícito del usuario: no quiere tener que
entrar a mirar la web para enterarse.

Depende de que `pool_puntos` ya esté actualizado hoy — va DESPUÉS de
scraper_puntos_pool en el cron diario (ver ingesta-diaria.yml).

Cada jugador se avisa como mucho una vez en la vida (dedup en
chollos_avisados, append-only) — sin esto, según baja de precio o sube de
puntos el mercado, el mismo top-3 por posición se repetiría cada día.
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
            print("OK: pool_puntos todavía vacío, nada que avisar.")
            return

        precios = leer_hoja("precios_diarios")
        if not precios:
            print("OK: precios_diarios todavía vacío, nada que avisar.")
            return
        fecha_max = max(f.get("fecha", "") for f in precios)
        snapshot = [f for f in precios if f.get("fecha") == fecha_max]

        mi_plantilla = leer_mi_plantilla()
        top = top_refuerzos_por_posicion(pool, snapshot, mi_plantilla)

        ya_avisados = {normalizar(f.get("jugador", "")) for f in leer_chollos_avisados()}
        nuevos = [c for c in top if normalizar(c.jugador) not in ya_avisados]

        if not nuevos:
            print("OK: sin chollos nuevos hoy.")
            return

        lineas = [
            f"💎 {c.jugador} ({c.equipo}, {c.posicion}) — {c.puntos_por_millon:.1f} pts/M€, "
            f"{c.puntos} puntos, {c.valor:,.0f}€".replace(",", ".")
            for c in nuevos
        ]
        enviar_mensaje("🔎 Chollos nuevos que podrían reforzar tu plantilla:\n\n" + "\n".join(lineas))

        hoy = dt.date.today().isoformat()
        append_chollos_avisados([[hoy, c.jugador, c.posicion, round(c.puntos_por_millon, 2)] for c in nuevos])
        print(f"OK: avisados {len(nuevos)} chollos nuevos.")
    except Exception as err:
        notificar_fallo("aviso_chollos", err)
        raise


if __name__ == "__main__":
    main()
