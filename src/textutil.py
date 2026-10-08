"""Normalización de nombres de jugadores para cruces por texto libre.

Compartido entre la app de Streamlit y los scrapers: cualquier sitio que
necesite comparar un nombre escrito a mano contra uno scrapeado usa esto.
"""
from __future__ import annotations

import re
import unicodedata


def normalizar(texto: str) -> str:
    texto = str(texto or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def slug(texto: str) -> str:
    """'Lamine Yamal' -> 'lamine-yamal'. Reconstruye la URL de perfil de
    futbolfantasy.com a partir del nombre — la web no expone esa URL en las
    filas de la tabla de mercado, solo en páginas de lesionados/sancionados."""
    return re.sub(r"[^a-z0-9]+", "-", normalizar(texto)).strip("-")
