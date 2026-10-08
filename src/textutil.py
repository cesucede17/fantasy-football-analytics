"""Player name normalization for free-text matching.

Shared between the Streamlit app and the scrapers: anywhere a hand-typed
name needs to be matched against a scraped one uses this.
"""
from __future__ import annotations

import re
import unicodedata


def normalizar(texto: str) -> str:
    texto = str(texto or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def slug(texto: str) -> str:
    """'Lamine Yamal' -> 'lamine-yamal'. Reconstructs futbolfantasy.com's
    profile URL from the player's name — the site doesn't expose that URL
    in the market table's rows, only on injury/suspension pages."""
    return re.sub(r"[^a-z0-9]+", "-", normalizar(texto)).strip("-")
