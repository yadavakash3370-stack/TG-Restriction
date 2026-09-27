"""Configuration - loads env vars + persistent data paths"""
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

BOT_SIGNATURE = os.getenv("BOT_SIGNATURE", "Extracted by @XyrDeveloper")
BANDWIDTH_LIMIT_GB = float(os.getenv("BANDWIDTH_LIMIT_GB", "4.5"))
BANDWIDTH_LIMIT_BYTES = int(BANDWIDTH_LIMIT_GB * 1024 * 1024 * 1024)

PORT = int(os.getenv("PORT", "8080"))

BOT_SESSION_NAME = "copier_bot"
USER_SESSION_NAME = "copier_user"

# Persistent storage directory (survives Render restart)
DATA_DIR = os.getenv("DATA_DIR", "data")
SESSION_FILE = os.path.join(DATA_DIR, "user_session.txt")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
BANDWIDTH_FILE = os.path.join(DATA_DIR, "bandwidth.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs("downloads", exist_ok=True)
os.makedirs("logs", exist_ok=True)


def validate_config():
    errors = []
    if not API_ID:
        errors.append("API_ID missing")
    if not API_HASH:
        errors.append("API_HASH missing")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN missing")
    if not OWNER_ID:
        errors.append("OWNER_ID missing")
    if errors:
        raise ValueError(f"Config errors: {', '.join(errors)}")
    return True
