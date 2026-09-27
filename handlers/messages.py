"""Non-command message handlers (OTP input, channel selection, link paste)"""
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from auth.permissions import permissions
from auth.session_manager import session_mgr, SessionState
from core.channel_manager import channel_mgr
from core.copy_engine import copy_engine
from core.bandwidth import bandwidth
from utils.logger import logger


# ==================== LOGIN FLOW MESSAGES ====================

async def handle_login_input(client: Client, message: Message):
    """Handle phone number, OTP code, and 2FA password inputs"""
    user_id = message.from_user.id
    
    # Only owner/admin can login
    if not permissions.is_admin_or_higher(user_id):
        return
    
    text = message.text.strip()
    
    # Ignore commands
    if text.startswith("/"):
        return
    
    state = session_mgr.login_state
    
    if state == SessionState.AWAITING_PHONE:
        # Expecting phone number
        if not text.startswith("+"):
            await message.reply_text(
                "❌ Phone number must start with + and country code.\n"
                "Example: `+919876543210`"
            )
            return
        
        status_msg = await message.reply_text("📤 Sending OTP...")
        success, msg_text = await session_mgr.start_phone_login(text)
        await status_msg.edit_text(f"{'✅' if success else '❌'} {msg_text}")
    
    elif state == SessionState.AWAITING_CODE:
        # Expecting OTP code
        clean_code = text.replace(" ", "").replace("-", "").strip()
        if not clean_code.isdigit():
            await message.reply_text("❌ Code should be numeric.")
            return
        
        status_msg = await message.reply_text("🔐 Verifying code...")
        success, msg_text = await session_mgr.verify_code(clean_code)
        await status_msg.edit_text(f"{'✅' if success else '❌'} {msg_text}")
    
    elif state == SessionState.AWAITING_PASSWORD:
        # Expecting 2FA password
        try:
            await message.delete()  # Delete password for security
        except Exception:
            pass
        
        status_msg = await client.send_message(
            message.chat.id, "🔐 Checking password..."
        )
        success, msg_text = await session_mgr.verify_password(text)
        await status_msg.edit_text(f"{'✅' if success else '❌'} {msg_text}")


# ==================== CHANNEL SELECTION ====================

async def handle_channel_selection(client: Client, message: Message):
    """Handle numeric input when selecting from search results"""
    user_id = message.from_user.id
    
    if not permissions.is_admin_or_higher(user_id):
        return
    
    text = message.text.strip()
    
    if not text.isdigit():
        return
    
    if not channel_mgr.pending_search_results:
        return
    
    idx = int(text) - 1
    if idx < 0 or idx >= len(channel_mgr.pending_search_results):
        await message.reply_text(
            f"❌ Invalid choice. Pick 1 to {len(channel_mgr.pending_search_results)}."
        )
        return
    
    chat = channel_mgr.pending_search_results[idx]
    selection_type = channel_mgr.pending_search_type
    
    # Clear pending
    channel_mgr.pending_search_results = []
    channel_mgr.pending_search_type = None
    
    if selection_type == "source":
        channel_mgr.set_source(chat)
        await message.reply_text(
            f"✅ **Source Connected!**\n\n"
            f"📥 {chat.title}\n"
            f"🆔 `{chat.id}`\n\n"
            f"Use /analyze to scan content."
        )
    elif selection_type == "destination":
        channel_mgr.set_destination(chat)
        await message.reply_text(
            f"✅ **Destination Set!**\n\n"
            f"📤 {chat.title}\n"
            f"🆔 `{chat.id}`"
        )


# ==================== TELEGRAM LINK COPY ====================

TG_LINK_PATTERN = re.compile(
    r"https?://t\.me/(?:c/)?([\w\d_]+)/(\d+)"
)


async def handle_telegram_link(client: Client, message: Message):
    """Handle pasted Telegram message links - copies that message"""
    user_id = message.from_user.id
    
    if not permissions.is_admin_or_higher(user_id):
        return
    
    text = message.text or ""
    matches = TG_LINK_PATTERN.findall(text)
    
    if not matches:
        return
    
    if not session_mgr.is_logged_in:
        await message.reply_text("❌ Please login first.")
        return
    
    if not channel_mgr.destination_chat:
        await message.reply_text("❌ Please set destination with /setdest first.")
        return
    
    for chat_ref, msg_id_str in matches:
        try:
            msg_id = int(msg_id_str)
            
            # Resolve chat
            if chat_ref.isdigit():
                # Private channel format: /c/12345/678
                source_id = int(f"-100{chat_ref}")
            else:
                # Public: /username/678
                try:
                    chat = await session_mgr.user_client.get_chat(chat_ref)
                    source_id = chat.id
                except Exception as e:
                    await message.reply_text(f"❌ Cannot access {chat_ref}: {e}")
                    continue
            
            status_msg = await message.reply_text(f"⏳ Copying message {msg_id}...")
            
            success, status_text, bytes_used = await copy_engine.copy_single_message(
                user_client=session_mgr.user_client,
                bot_client=client,
                source_chat_id=source_id,
                message_id=msg_id,
                dest_chat_id=channel_mgr.destination_chat.id,
            )
            
            if success:
                await status_msg.edit_text(
                    f"✅ **Copied!**\n"
                    f"📊 {status_text}\n"
                    f"💾 Bandwidth: `{bytes_used / (1024*1024):.2f} MB`"
                )
            else:
                await status_msg.edit_text(f"❌ Failed: {status_text}")
        
        except Exception as e:
            logger.error(f"Link copy error: {e}")
            await message.reply_text(f"❌ Error: {e}")


# ==================== REGISTER HANDLERS ====================

def register_message_handlers(app: Client):
    """Register all message (non-command) handlers"""
    
    # Login flow - text messages when in login state
    app.add_handler(
        MessageHandler(
            handle_login_input,
            filters.text & filters.private & ~filters.command([
                "start", "help", "status", "login", "session", "logout",
                "connect", "setdest", "disconnect", "analyze",
                "copy", "v", "p", "d", "a", "pause", "resume", "stop", "skip",
                "mode", "limit", "reset", "progress", "speed",
                "adduser", "addadmin", "removeuser", "removeadmin",
                "userlist", "broadcast", "cancel",
            ]),
        )
    )
    
    # Channel selection - numeric input
    app.add_handler(
        MessageHandler(
            handle_channel_selection,
            filters.text & filters.regex(r"^\d+$"),
        )
    )
    
    # Telegram link paste
    app.add_handler(
        MessageHandler(
            handle_telegram_link,
            filters.text & filters.regex(TG_LINK_PATTERN.pattern),
        )
    )
    
    logger.info("Message handlers registered")
