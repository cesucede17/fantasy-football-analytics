"""Backfill único: clasificación final de LaLiga 2025/26.

No es un scraper que se ejecute a diario — es un dato histórico fijo que no
cambia, así que se guarda una vez a mano (aquí, como constante) en vez de
montar infraestructura para volver a por él. Sirve de punto de partida al
empezar la temporada 2026/27, cuando `calendario_resultados` todavía no
tiene partidos jugados suficientes para calcular una clasificación real —
ver `src.analisis.enfrentamientos.tabla_posiciones`.

Nombres de equipo normalizados a como los usa futbolfantasy.com (misma
fuente que el resto del proyecto), no a los nombres oficiales largos de la
Wikipedia (de donde sale este dato): "Atlético Madrid" -> "Atlético", etc.

Fuente: https://en.wikipedia.org/wiki/2025%E2%80%9326_La_Liga (temporada
ya concluida en el momento de este backfill).
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
    ("Mallorca", 18),  # descendido
    ("Girona", 19),  # descendido
    ("Real Oviedo", 20),  # descendido
]


def a_filas() -> list[list]:
    return [[equipo, posicion, "2025/26"] for equipo, posicion in CLASIFICACION_2025_26]


def main() -> None:
    from src.storage.sheets import sobrescribir_clasificacion_anterior

    sobrescribir_clasificacion_anterior(a_filas())
    print(f"OK: clasificación 2025/26 guardada ({len(CLASIFICACION_2025_26)} equipos).")


if __name__ == "__main__":
    main()
