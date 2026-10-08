"""One-off backfill: LaLiga 2025/26 final standings.

Not a scraper that runs daily — it's a fixed historical fact that never
changes, so it's stored once by hand (here, as a constant) instead of
building infrastructure to fetch it again. Serves as the starting point at
the beginning of the 2026/27 season, while `calendario_resultados` doesn't
yet have enough played matches to compute a real table — see
`src.analisis.enfrentamientos.tabla_posiciones`.

Team names normalized to how futbolfantasy.com uses them (same source as
the rest of the project), not Wikipedia's official long-form names (where
this data comes from): "Atlético Madrid" -> "Atlético", etc.

Source: https://en.wikipedia.org/wiki/2025%E2%80%9326_La_Liga (season
already finished at the time of this backfill).
"""
from __future__ import annotations

CLASIFICACION_2025_26 = [
    ("Barcelona", 1),
    ("Real Madrid", 2),
    ("Villarreal", 3),
    ("Atlético", 4),
    ("Betis", 5),
    ("Celta", 6),
    ("Getafe", 7),
    ("Rayo", 8),
    ("Valencia", 9),
    ("Real Sociedad", 10),
    ("Espanyol", 11),
    ("Athletic", 12),
    ("Sevilla", 13),
    ("Alavés", 14),
    ("Elche", 15),
    ("Levante", 16),
    ("Osasuna", 17),
    ("Mallorca", 18),  # relegated
    ("Girona", 19),  # relegated
    ("Real Oviedo", 20),  # relegated
]


def a_filas() -> list[list]:
    return [[equipo, posicion, "2025/26"] for equipo, posicion in CLASIFICACION_2025_26]


def main() -> None:
    from src.storage.sheets import sobrescribir_clasificacion_anterior

    sobrescribir_clasificacion_anterior(a_filas())
    print(f"OK: 2025/26 standings saved ({len(CLASIFICACION_2025_26)} teams).")


if __name__ == "__main__":
    main()
