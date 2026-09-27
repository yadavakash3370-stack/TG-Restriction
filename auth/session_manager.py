
"""Session manager with FILE-BASED persistence (survives restart)"""
import os
from typing import Optional
from pyrogram import Client
from pyrogram.errors import (
    SessionPasswordNeeded,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    PhoneNumberInvalid,
)
from config import (
    API_ID, API_HASH, USER_SESSION_NAME,
    SESSION_FILE, DATA_DIR,
)
from utils.logger import logger


class SessionState:
    IDLE = "idle"
    AWAITING_PHONE = "awaiting_phone"
    AWAITING_CODE = "awaiting_code"
    AWAITING_PASSWORD = "awaiting_password"


class UserSessionManager:
    def __init__(self):
        self.user_client: Optional[Client] = None
        self.is_logged_in: bool = False
        self.account_info: dict = {}
        self.login_state: str = SessionState.IDLE
        self.pending_phone: Optional[str] = None
        self.pending_phone_code_hash: Optional[str] = None
        self.temp_client: Optional[Client] = None

    def _save_session_string(self, session_string: str):
        """Save session string to file for persistence"""
        try:
            with open(SESSION_FILE, "w") as f:
                f.write(session_string)
            logger.info("Session string saved to file")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    def _load_session_string(self) -> Optional[str]:
        """Load session string from file"""
        try:
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, "r") as f:
                    session = f.read().strip()
                if session:
                    logger.info("Session string loaded from file")
                    return session
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
        return None

    def _delete_session_file(self):
        """Delete saved session"""
        try:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
                logger.info("Session file deleted")
        except Exception:
            pass

    async def auto_login_from_file(self) -> bool:
        """Auto-login from saved session file on startup"""
        session_string = self._load_session_string()
        if not session_string:
            logger.info("No saved session found")
            return False

        success, msg = await self.login_with_session_string(session_string)
        if success:
            logger.info("Auto-login successful from saved session")
            return True
        else:
            logger.warning(f"Auto-login failed: {msg}")
            self._delete_session_file()
            return False

    async def login_with_session_string(self, session_string: str) -> tuple:
        """Login using session string + save to file"""
        try:
            if self.user_client:
                await self.logout()

            client = Client(
                name=USER_SESSION_NAME,
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_string,
                in_memory=True,
            )
            await client.start()
            me = await client.get_me()

            self.user_client = client
            self.is_logged_in = True
            self.account_info = {
                "id": me.id,
                "name": f"{me.first_name} {me.last_name or ''}".strip(),
                "username": me.username,
                "phone": me.phone_number,
            }

            # SAVE to file for persistence
            self._save_session_string(session_string)

            logger.info(f"Logged in: {self.account_info['name']}")
            return True, f"Logged in as {self.account_info['name']}"

        except Exception as e:
            logger.error(f"Session login failed: {e}")
            return False, f"Login failed: {str(e)}"

    async def start_phone_login(self, phone_number: str) -> tuple:
        try:
            if self.temp_client:
                try:
                    await self.temp_client.disconnect()
                except Exception:
                    pass

            self.temp_client = Client(
                name=USER_SESSION_NAME,
                api_id=API_ID,
                api_hash=API_HASH,
                in_memory=True,
            )
            await self.temp_client.connect()
            sent_code = await self.temp_client.send_code(phone_number)

            self.pending_phone = phone_number
            self.pending_phone_code_hash = sent_code.phone_code_hash
            self.login_state = SessionState.AWAITING_CODE

            return True, "OTP sent! Send the code now."
        except PhoneNumberInvalid:
            return False, "Invalid phone number."
        except Exception as e:
            return False, f"Failed: {str(e)}"

    async def verify_code(self, code: str) -> tuple:
        if not self.temp_client or not self.pending_phone:
            return False, "No pending login. Use /login first."

        try:
            clean_code = code.replace(" ", "").replace("-", "").strip()
            await self.temp_client.sign_in(
                phone_number=self.pending_phone,
                phone_code_hash=self.pending_phone_code_hash,
                phone_code=clean_code,
            )

            me = await self.temp_client.get_me()
            self.user_client = self.temp_client
            self.temp_client = None
            self.is_logged_in = True
            self.account_info = {
                "id": me.id,
                "name": f"{me.first_name} {me.last_name or ''}".strip(),
                "username": me.username,
                "phone": me.phone_number,
            }

            self.login_state = SessionState.IDLE
            self.pending_phone = None
            self.pending_phone_code_hash = None

            # Export and save session string
            try:
                session_string = await self.user_client.export_session_string()
                self._save_session_string(session_string)
            except Exception as e:
                logger.warning(f"Could not export session: {e}")

            return True, f"Login successful! {self.account_info['name']}"

        except SessionPasswordNeeded:
            self.login_state = SessionState.AWAITING_PASSWORD
            return False, "2FA enabled. Send your password."
        except (PhoneCodeInvalid, PhoneCodeExpired):
            return False, "Invalid or expired code."
        except Exception as e:
            return False, f"Failed: {str(e)}"

    async def verify_password(self, password: str) -> tuple:
        if not self.temp_client:
            return False, "No pending login."
        try:
            await self.temp_client.check_password(password)
            me = await self.temp_client.get_me()

            self.user_client = self.temp_client
            self.temp_client = None
            self.is_logged_in = True
            self.account_info = {
                "id": me.id,
                "name": f"{me.first_name} {me.last_name or ''}".strip(),
                "username": me.username,
                "phone": me.phone_number,
            }

            self.login_state = SessionState.IDLE

            try:
                session_string = await self.user_client.export_session_string()
                self._save_session_string(session_string)
            except Exception:
                pass

            return True, f"Login successful! {self.account_info['name']}"
        except Exception as e:
            return False, f"Password failed: {str(e)}"

    async def logout(self) -> tuple:
        try:
            if self.user_client:
                try:
                    await self.user_client.log_out()
                except Exception:
                    pass
                try:
                    await self.user_client.stop()
                except Exception:
                    pass

            self.user_client = None
            self.is_logged_in = False
            self.account_info = {}
            self.login_state = SessionState.IDLE
            self._delete_session_file()

            return True, "Logged out."
        except Exception as e:
            return False, f"Logout error: {str(e)}"

    def get_status(self) -> str:
        if not self.is_logged_in:
            return "❌ Not logged in"
        return (
            f"✅ Logged in\n"
            f"👤 {self.account_info.get('name', 'N/A')}\n"
            f"🆔 `{self.account_info.get('id', 'N/A')}`\n"
            f"📱 {self.account_info.get('phone', 'N/A')}"
        )


session_mgr = UserSessionManager()
