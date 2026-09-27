"""Configuration file - loads environment variables"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API credentials
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Owner
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Bot signature (added to every copied message)
BOT_SIGNATURE = os.getenv("BOT_SIGNATURE", "Extracted by @XyrDeveloper")

# Bandwidth limit (in bytes)
BANDWIDTH_LIMIT_GB = float(os.getenv("BANDWIDTH_LIMIT_GB", "4.5"))
BANDWIDTH_LIMIT_BYTES = int(BANDWIDTH_LIMIT_GB * 1024 * 1024 * 1024)

# Web service port (for Render)
PORT = int(os.getenv("PORT", "8080"))

# Bot session name
BOT_SESSION_NAME = "copier_bot"
USER_SESSION_NAME = "copier_user"

# Validate required config
def validate_config():
    """Validate that all required configuration is present"""
    errors = []
    if not API_ID:
        errors.append("API_ID is missing")
    if not API_HASH:
        errors.append("API_HASH is missing")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is missing")
    if not OWNER_ID:
        errors.append("OWNER_ID is missing")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    return True
