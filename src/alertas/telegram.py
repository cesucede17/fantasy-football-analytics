"""Sending alerts via Telegram.

Planned alert types:
  - market bargain
  - sell window
  - early news (injury published, price hasn't reacted yet)
  - release-clause risk / shield priority
  - lineup reminder
  - SYSTEM FAILURE (broken scraper, failed workflow)

The last one isn't optional: a scraper that fails silently gets discovered
too late.
"""
from __future__ import annotations

import requests

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def enviar_mensaje(texto: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url, data={"chat_id": TELEGRAM_CHAT_ID, "text": texto}, timeout=15
    )
    resp.raise_for_status()


def notificar_fallo(origen: str, error: Exception) -> None:
    """Reports a system failure. Doesn't re-raise if the alert itself
    fails (avoids a down Telegram hiding the original error in the logs)."""
    texto = f"⚠️ Failure in {origen}\n{type(error).__name__}: {error}"
    try:
        enviar_mensaje(texto)
    except Exception:
        pass
