"""One-off backfill: complete LaLiga 2025/26 results, so the head-to-head
history has something to work with from day one of the 2026/27 season —
with 0-3 matchdays played in the new season, almost no pair of teams has
faced each other yet.

Not a scraper that runs daily: it's a fixed historical fact. Added to
`calendario_resultados` (the same tab `scraper_calendario` writes to, with
temporada="2025/26") without overwriting the current season's matches —
both this script and `scraper_calendario` re-read what's already stored and
only replace their own season's rows before writing, so they can run in
any order without one erasing the other's work.

The real matchday for each match isn't known (the source is a results
matrix, not a chronological schedule), so `jornada=0` is stored — that's
fine for the head-to-head history (it doesn't depend on in-season order),
but it isn't used for a team's "recent form" (that function only looks at
each team's most recent season).

Source: https://en.wikipedia.org/wiki/2025%E2%80%9326_La_Liga (results
table, season already finished).
"""
from __future__ import annotations

import re

TEMPORADA = "2025/26"

# "Home X-Y Away" — one line per match, 380 total (20 teams, home and away).
# Names exactly as the source (Wikipedia) gives them; normalized to
# futbolfantasy.com's short naming in ALIAS.
RESULTADOS_TEXTO = """
Alavés 2-4 Athletic Bilbao
Alavés 1-1 Atlético Madrid
Alavés 1-0 Barcelona
Alavés 0-1 Celta Vigo
Alavés 3-1 Elche
Alavés 2-1 Espanyol
Alavés 0-2 Getafe
Alavés 2-2 Girona
Alavés 2-1 Levante
Alavés 2-1 Mallorca
Alavés 2-2 Osasuna
Alavés 1-1 Oviedo
Alavés 1-2 Rayo Vallecano
Alavés 2-1 Real Betis
Alavés 1-2 Real Madrid
Alavés 1-0 Real Sociedad
Alavés 1-2 Sevilla
Alavés 0-0 Valencia
Alavés 1-1 Villarreal
Athletic Bilbao 0-1 Alavés
Athletic Bilbao 1-0 Atlético Madrid
Athletic Bilbao 0-1 Barcelona
Athletic Bilbao 1-1 Celta Vigo
Athletic Bilbao 2-1 Elche
Athletic Bilbao 1-2 Espanyol
Athletic Bilbao 0-1 Getafe
Athletic Bilbao 1-1 Girona
Athletic Bilbao 4-2 Levante
Athletic Bilbao 2-1 Mallorca
Athletic Bilbao 1-0 Osasuna
Athletic Bilbao 1-0 Oviedo
Athletic Bilbao 2-1 Rayo Vallecano
Athletic Bilbao 0-3 Real Betis
Athletic Bilbao 1-1 Real Madrid
Athletic Bilbao 3-2 Real Sociedad
Athletic Bilbao 0-1 Sevilla
Athletic Bilbao 1-2 Valencia
Athletic Bilbao 1-2 Villarreal
Atlético Madrid 1-0 Alavés
Atlético Madrid 3-2 Athletic Bilbao
Atlético Madrid 1-2 Barcelona
Atlético Madrid 0-1 Celta Vigo
Atlético Madrid 1-1 Elche
Atlético Madrid 4-2 Espanyol
Atlético Madrid 1-0 Getafe
Atlético Madrid 1-0 Girona
Atlético Madrid 3-1 Levante
Atlético Madrid 3-0 Mallorca
Atlético Madrid 1-0 Osasuna
Atlético Madrid 2-0 Oviedo
Atlético Madrid 3-2 Rayo Vallecano
Atlético Madrid 0-1 Real Betis
Atlético Madrid 5-2 Real Madrid
Atlético Madrid 3-2 Real Sociedad
Atlético Madrid 3-0 Sevilla
Atlético Madrid 2-1 Valencia
Atlético Madrid 2-0 Villarreal
Barcelona 3-1 Alavés
Barcelona 4-0 Athletic Bilbao
Barcelona 3-1 Atlético Madrid
Barcelona 1-0 Celta Vigo
Barcelona 3-1 Elche
Barcelona 4-1 Espanyol
Barcelona 3-0 Getafe
Barcelona 2-1 Girona
Barcelona 3-0 Levante
Barcelona 3-0 Mallorca
Barcelona 2-0 Osasuna
Barcelona 3-0 Oviedo
Barcelona 1-0 Rayo Vallecano
Barcelona 3-1 Real Betis
Barcelona 2-0 Real Madrid
Barcelona 2-1 Real Sociedad
Barcelona 5-2 Sevilla
Barcelona 6-0 Valencia
Barcelona 4-1 Villarreal
Celta Vigo 3-4 Alavés
Celta Vigo 2-0 Athletic Bilbao
Celta Vigo 1-1 Atlético Madrid
Celta Vigo 2-4 Barcelona
Celta Vigo 3-1 Elche
Celta Vigo 0-1 Espanyol
Celta Vigo 0-2 Getafe
Celta Vigo 1-1 Girona
Celta Vigo 2-3 Levante
Celta Vigo 2-0 Mallorca
Celta Vigo 1-2 Osasuna
Celta Vigo 0-3 Oviedo
Celta Vigo 3-0 Rayo Vallecano
Celta Vigo 1-1 Real Betis
Celta Vigo 1-2 Real Madrid
Celta Vigo 1-1 Real Sociedad
Celta Vigo 1-0 Sevilla
Celta Vigo 4-1 Valencia
Celta Vigo 1-1 Villarreal
Elche 1-1 Alavés
Elche 0-0 Athletic Bilbao
Elche 3-2 Atlético Madrid
Elche 1-3 Barcelona
Elche 2-1 Celta Vigo
Elche 2-2 Espanyol
Elche 1-0 Getafe
Elche 3-0 Girona
Elche 2-0 Levante
Elche 2-1 Mallorca
Elche 0-0 Osasuna
Elche 1-0 Oviedo
Elche 4-0 Rayo Vallecano
Elche 1-1 Real Betis
Elche 2-2 Real Madrid
Elche 1-1 Real Sociedad
Elche 2-2 Sevilla
Elche 1-0 Valencia
Elche 1-3 Villarreal
Espanyol 1-2 Alavés
Espanyol 2-0 Athletic Bilbao
Espanyol 2-1 Atlético Madrid
Espanyol 0-2 Barcelona
Espanyol 2-2 Celta Vigo
Espanyol 1-0 Elche
Espanyol 1-2 Getafe
Espanyol 0-2 Girona
Espanyol 0-0 Levante
Espanyol 3-2 Mallorca
Espanyol 1-0 Osasuna
Espanyol 1-1 Oviedo
Espanyol 1-0 Rayo Vallecano
Espanyol 1-2 Real Betis
Espanyol 0-2 Real Madrid
Espanyol 1-1 Real Sociedad
Espanyol 2-1 Sevilla
Espanyol 2-2 Valencia
Espanyol 0-2 Villarreal
Getafe 1-1 Alavés
Getafe 2-0 Athletic Bilbao
Getafe 0-1 Atlético Madrid
Getafe 0-2 Barcelona
Getafe 0-0 Celta Vigo
Getafe 1-0 Elche
Getafe 0-1 Espanyol
Getafe 2-1 Girona
Getafe 1-1 Levante
Getafe 3-1 Mallorca
Getafe 1-0 Osasuna
Getafe 2-0 Oviedo
Getafe 0-2 Rayo Vallecano
Getafe 2-0 Real Betis
Getafe 0-1 Real Madrid
Getafe 1-2 Real Sociedad
Getafe 0-1 Sevilla
Getafe 0-1 Valencia
Getafe 2-1 Villarreal
Girona 1-0 Alavés
Girona 3-0 Athletic Bilbao
Girona 0-3 Atlético Madrid
Girona 2-1 Barcelona
Girona 1-2 Celta Vigo
Girona 1-1 Elche
Girona 0-0 Espanyol
Girona 1-1 Getafe
Girona 0-4 Levante
Girona 0-1 Mallorca
Girona 1-0 Osasuna
Girona 3-3 Oviedo
Girona 1-3 Rayo Vallecano
Girona 2-3 Real Betis
Girona 1-1 Real Madrid
Girona 1-1 Real Sociedad
Girona 0-2 Sevilla
Girona 2-1 Valencia
Girona 1-0 Villarreal
Levante 2-0 Alavés
Levante 0-2 Athletic Bilbao
Levante 0-0 Atlético Madrid
Levante 2-3 Barcelona
Levante 1-2 Celta Vigo
Levante 3-2 Elche
Levante 1-1 Espanyol
Levante 1-0 Getafe
Levante 1-1 Girona
Levante 2-0 Mallorca
Levante 3-2 Osasuna
Levante 4-2 Oviedo
Levante 0-3 Rayo Vallecano
Levante 2-2 Real Betis
Levante 1-4 Real Madrid
Levante 1-1 Real Sociedad
Levante 2-0 Sevilla
Levante 0-2 Valencia
Levante 0-1 Villarreal
Mallorca 1-0 Alavés
Mallorca 3-2 Athletic Bilbao
Mallorca 1-1 Atlético Madrid
Mallorca 0-3 Barcelona
Mallorca 1-1 Celta Vigo
Mallorca 3-1 Elche
Mallorca 2-1 Espanyol
Mallorca 1-0 Getafe
Mallorca 1-2 Girona
Mallorca 1-1 Levante
Mallorca 2-2 Osasuna
Mallorca 3-0 Oviedo
Mallorca 3-0 Rayo Vallecano
Mallorca 1-2 Real Betis
Mallorca 2-1 Real Madrid
Mallorca 0-1 Real Sociedad
Mallorca 4-1 Sevilla
Mallorca 1-1 Valencia
Mallorca 1-1 Villarreal
Osasuna 3-0 Alavés
Osasuna 1-1 Athletic Bilbao
Osasuna 1-2 Atlético Madrid
Osasuna 1-2 Barcelona
Osasuna 2-3 Celta Vigo
Osasuna 1-1 Elche
Osasuna 1-2 Espanyol
Osasuna 2-1 Getafe
Osasuna 1-0 Girona
Osasuna 2-0 Levante
Osasuna 2-2 Mallorca
Osasuna 3-2 Oviedo
Osasuna 2-0 Rayo Vallecano
Osasuna 1-1 Real Betis
Osasuna 1-1 Real Madrid
Osasuna 2-1 Real Sociedad
Osasuna 1-3 Sevilla
Osasuna 2-1 Valencia
Osasuna 1-0 Villarreal
Oviedo 0-1 Alavés
Oviedo 1-2 Athletic Bilbao
Oviedo 0-1 Atlético Madrid
Oviedo 1-3 Barcelona
Oviedo 0-0 Celta Vigo
Oviedo 1-2 Elche
Oviedo 0-2 Espanyol
Oviedo 0-0 Getafe
Oviedo 1-0 Girona
Oviedo 0-2 Levante
Oviedo 0-0 Mallorca
Oviedo 0-0 Osasuna
Oviedo 0-0 Rayo Vallecano
Oviedo 1-1 Real Betis
Oviedo 0-3 Real Madrid
Oviedo 1-0 Real Sociedad
Oviedo 1-0 Sevilla
Oviedo 1-0 Valencia
Oviedo 1-1 Villarreal
Rayo Vallecano 1-0 Alavés
Rayo Vallecano 1-1 Athletic Bilbao
Rayo Vallecano 3-0 Atlético Madrid
Rayo Vallecano 1-1 Barcelona
Rayo Vallecano 1-1 Celta Vigo
Rayo Vallecano 1-0 Elche
Rayo Vallecano 1-0 Espanyol
Rayo Vallecano 1-1 Getafe
Rayo Vallecano 1-1 Girona
Rayo Vallecano 1-1 Levante
Rayo Vallecano 2-1 Mallorca
Rayo Vallecano 1-3 Osasuna
Rayo Vallecano 3-0 Oviedo
Rayo Vallecano 0-0 Real Betis
Rayo Vallecano 0-0 Real Madrid
Rayo Vallecano 3-3 Real Sociedad
Rayo Vallecano 0-1 Sevilla
Rayo Vallecano 1-1 Valencia
Rayo Vallecano 2-0 Villarreal
Real Betis 1-0 Alavés
Real Betis 1-2 Athletic Bilbao
Real Betis 0-2 Atlético Madrid
Real Betis 3-5 Barcelona
Real Betis 1-1 Celta Vigo
Real Betis 2-1 Elche
Real Betis 0-0 Espanyol
Real Betis 4-0 Getafe
Real Betis 1-1 Girona
Real Betis 2-1 Levante
Real Betis 3-0 Mallorca
Real Betis 2-0 Osasuna
Real Betis 3-0 Oviedo
Real Betis 1-1 Rayo Vallecano
Real Betis 1-1 Real Madrid
Real Betis 3-1 Real Sociedad
Real Betis 2-2 Sevilla
Real Betis 2-1 Valencia
Real Betis 2-0 Villarreal
Real Madrid 2-1 Alavés
Real Madrid 4-2 Athletic Bilbao
Real Madrid 3-2 Atlético Madrid
Real Madrid 2-1 Barcelona
Real Madrid 0-2 Celta Vigo
Real Madrid 4-1 Elche
Real Madrid 2-0 Espanyol
Real Madrid 0-1 Getafe
Real Madrid 1-1 Girona
Real Madrid 2-0 Levante
Real Madrid 2-1 Mallorca
Real Madrid 1-0 Osasuna
Real Madrid 2-0 Oviedo
Real Madrid 2-1 Rayo Vallecano
Real Madrid 5-1 Real Betis
Real Madrid 4-1 Real Sociedad
Real Madrid 2-0 Sevilla
Real Madrid 4-0 Valencia
Real Madrid 3-1 Villarreal
Real Sociedad 3-3 Alavés
Real Sociedad 3-2 Athletic Bilbao
Real Sociedad 1-1 Atlético Madrid
Real Sociedad 2-1 Barcelona
Real Sociedad 3-1 Celta Vigo
Real Sociedad 3-1 Elche
Real Sociedad 2-2 Espanyol
Real Sociedad 0-1 Getafe
Real Sociedad 1-2 Girona
Real Sociedad 2-0 Levante
Real Sociedad 1-0 Mallorca
Real Sociedad 3-1 Osasuna
Real Sociedad 3-3 Oviedo
Real Sociedad 0-1 Rayo Vallecano
Real Sociedad 2-2 Real Betis
Real Sociedad 1-2 Real Madrid
Real Sociedad 2-1 Sevilla
Real Sociedad 3-4 Valencia
Real Sociedad 2-3 Villarreal
Sevilla 1-1 Alavés
Sevilla 2-1 Athletic Bilbao
Sevilla 2-1 Atlético Madrid
Sevilla 4-1 Barcelona
Sevilla 0-1 Celta Vigo
Sevilla 2-2 Elche
Sevilla 2-1 Espanyol
Sevilla 1-2 Getafe
Sevilla 1-1 Girona
Sevilla 0-3 Levante
Sevilla 1-3 Mallorca
Sevilla 1-0 Osasuna
Sevilla 4-0 Oviedo
Sevilla 1-1 Rayo Vallecano
Sevilla 0-2 Real Betis
Sevilla 0-1 Real Madrid
Sevilla 1-0 Real Sociedad
Sevilla 0-2 Valencia
Sevilla 1-2 Villarreal
Valencia 3-2 Alavés
Valencia 2-0 Athletic Bilbao
Valencia 0-2 Atlético Madrid
Valencia 3-1 Barcelona
Valencia 2-3 Celta Vigo
Valencia 1-1 Elche
Valencia 3-2 Espanyol
Valencia 3-0 Getafe
Valencia 2-1 Girona
Valencia 1-0 Levante
Valencia 1-1 Mallorca
Valencia 1-0 Osasuna
Valencia 1-2 Oviedo
Valencia 1-1 Rayo Vallecano
Valencia 1-1 Real Betis
Valencia 0-2 Real Madrid
Valencia 1-1 Real Sociedad
Valencia 1-1 Sevilla
Valencia 0-2 Villarreal
Villarreal 3-1 Alavés
Villarreal 1-0 Athletic Bilbao
Villarreal 5-1 Atlético Madrid
Villarreal 0-2 Barcelona
Villarreal 2-1 Celta Vigo
Villarreal 2-1 Elche
Villarreal 4-1 Espanyol
Villarreal 2-0 Getafe
Villarreal 5-0 Girona
Villarreal 5-1 Levante
Villarreal 2-1 Mallorca
Villarreal 2-1 Osasuna
Villarreal 2-0 Oviedo
Villarreal 4-0 Rayo Vallecano
Villarreal 2-2 Real Betis
Villarreal 0-2 Real Madrid
Villarreal 3-1 Real Sociedad
Villarreal 2-3 Sevilla
Villarreal 2-1 Valencia
""".strip()

# Wikipedia uses the long/official name; the rest of the project (and this
# season's calendario_resultados) uses futbolfantasy's short one.
ALIAS = {
    "Atlético Madrid": "Atlético",
    "Athletic Bilbao": "Athletic",
    "Celta Vigo": "Celta",
    "Rayo Vallecano": "Rayo",
    "Real Betis": "Betis",
    "Oviedo": "Real Oviedo",
}

PATRON_LINEA = re.compile(r"^(.+?)\s+(\d+)-(\d+)\s+(.+)$")


def _alias(nombre: str) -> str:
    return ALIAS.get(nombre, nombre)


def parsear_resultados() -> list[list]:
    filas = []
    for linea in RESULTADOS_TEXTO.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        m = PATRON_LINEA.match(linea)
        if not m:
            raise ValueError(f"Unexpected line format: {linea!r}")
        local, goles_local, goles_visitante, visitante = m.groups()
        filas.append([TEMPORADA, 0, "", _alias(local), _alias(visitante), int(goles_local), int(goles_visitante), "si"])
    return filas


def main() -> None:
    from src.storage.sheets import leer_calendario_resultados, sobrescribir_calendario_resultados

    actuales = [
        [f.get("temporada"), f.get("jornada"), f.get("fecha"), f.get("equipo_local"), f.get("equipo_visitante"),
         f.get("goles_local"), f.get("goles_visitante"), f.get("jugado")]
        for f in leer_calendario_resultados()
        if f.get("temporada") != TEMPORADA  # avoids duplicating on re-run
    ]
    nuevas = parsear_resultados()
    sobrescribir_calendario_resultados(actuales + nuevas)
    print(f"OK: {len(nuevas)} matches from {TEMPORADA} added to calendario_resultados ({len(actuales) + len(nuevas)} rows total).")


if __name__ == "__main__":
    main()
