"""Carga de configuración desde .env (local) o variables de entorno (CI)."""
import os
from dotenv import load_dotenv

load_dotenv()

FANTASY_USER = os.getenv("FANTASY_USER")
FANTASY_PASS = os.getenv("FANTASY_PASS")
FANTASY_BASE_URL = os.getenv("FANTASY_BASE_URL")

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
