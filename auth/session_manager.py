"""Manages Pyrogram userbot session (login via phone/OTP or session string)"""
from typing import Optional
from pyrogram import Client
from pyrogram.errors import (
    SessionPasswordNeeded,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    PhoneNumberInvalid,
    AuthKeyUnregistered,
)
from config import API_ID, API_HASH, USER_SESSION_NAME
from utils.logger import logger


class SessionState:
    """Tracks login state for OTP-based login"""
    IDLE = "idle"
    AWAITING_PHONE = "awaiting_phone"
    AWAITING_CODE = "awaiting_code"
    AWAITING_PASSWORD = "awaiting_password"


class UserSessionManager:
    """Manages the userbot client (for search/copy operations)"""
    
    def __init__(self):
        self.user_client: Optional[Client] = None
        self.is_logged_in: bool = False
        self.account_info: dict = {}
        
        # Login state tracking
        self.login_state: str = SessionState.IDLE
        self.pending_phone: Optional[str] = None
        self.pending_phone_code_hash: Optional[str] = None
        self.temp_client: Optional[Client] = None
    
    async def login_with_session_string(self, session_string: str) -> tuple[bool, str]:
        """Login using a pre-generated session string"""
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
            
            logger.info(f"User logged in via session string: {self.account_info['name']}")
            return True, f"Logged in as {self.account_info['name']}"
        
        except Exception as e:
            logger.error(f"Session string login failed: {e}")
            return False, f"Login failed: {str(e)}"
    
    async def start_phone_login(self, phone_number: str) -> tuple[bool, str]:
        """Start phone-based login (send OTP)"""
        try:
            # Cleanup any existing temp client
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
            
            return True, "OTP sent to your Telegram account. Send the code (format: 1 2 3 4 5 or 12345)"
        
        except PhoneNumberInvalid:
            return False, "Invalid phone number format. Use +CountryCode Number"
        except Exception as e:
            logger.error(f"Send code failed: {e}")
            return False, f"Failed to send OTP: {str(e)}"
    
    async def verify_code(self, code: str) -> tuple[bool, str]:
        """Verify the OTP code"""
        if not self.temp_client or not self.pending_phone:
            return False, "No pending login. Use /login first"
        
        try:
            # Clean code (remove spaces/dashes)
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
            
            # Reset login state
            self.login_state = SessionState.IDLE
            self.pending_phone = None
            self.pending_phone_code_hash = None
            
            logger.info(f"User logged in via OTP: {self.account_info['name']}")
            return True, f"Login successful! Welcome {self.account_info['name']}"
        
        except SessionPasswordNeeded:
            self.login_state = SessionState.AWAITING_PASSWORD
            return False, "2FA enabled. Send your password now"
        
        except (PhoneCodeInvalid, PhoneCodeExpired) as e:
            return False, f"Invalid or expired code: {str(e)}"
        
        except Exception as e:
            logger.error(f"Verify code failed: {e}")
            return False, f"Verification failed: {str(e)}"
    
    async def verify_password(self, password: str) -> tuple[bool, str]:
        """Verify 2FA password"""
        if not self.temp_client:
            return False, "No pending login"
        
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
            self.pending_phone = None
            self.pending_phone_code_hash = None
            
            logger.info(f"2FA verified: {self.account_info['name']}")
            return True, f"Login successful! Welcome {self.account_info['name']}"
        
        except Exception as e:
            logger.error(f"2FA failed: {e}")
            return False, f"Password verification failed: {str(e)}"
    
    async def logout(self) -> tuple[bool, str]:
        """Logout the user session"""
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
            
            return True, "Logged out successfully"
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False, f"Logout error: {str(e)}"
    
    def get_status(self) -> str:
        """Get current session status"""
        if not self.is_logged_in:
            return "❌ Not logged in"
        return (
            f"✅ Logged in\n"
            f"👤 Name: {self.account_info.get('name', 'N/A')}\n"
            f"🆔 ID: `{self.account_info.get('id', 'N/A')}`\n"
            f"📱 Phone: {self.account_info.get('phone', 'N/A')}"
        )


# Global instance
session_mgr = UserSessionManager()
