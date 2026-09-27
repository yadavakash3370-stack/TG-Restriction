"""Message handlers (Link paste + Auto Delete + Auto Copy to Current Chat)"""
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from auth.permissions import permissions
from auth.session_manager import session_mgr, SessionState
from core.channel_manager import channel_mgr
from core.copy_engine import copy_engine
from core.bandwidth import bandwidth
from utils.logger import logger

# Supports single link: https://t.me/channel/123 or range: https://t.me/channel/10-20
# Also supports private links: https://t.me/c/1234567890/123
TG_LINK_PATTERN = re.compile(
    r"https?://t\.me/(?:c/)?([\w\d_]+)/(\d+)(?:-(\d+))?"
)


async def handle_login_input(client: Client, message: Message):
    """Handle login input only in private chat"""
    if message.chat.type.name != "PRIVATE":
        return
    
    user_id = permissions.get_user_id(message)
    if not permissions.is_admin_or_higher(user_id):
        return
    
    text = message.text.strip()
    if text.startswith("/"):
        return
    
    state = session_mgr.login_state
    
    if state == SessionState.AWAITING_PHONE:
        if not text.startswith("+"):
            await message.reply_text("❌ Number format: `+919876543210`")
            return
        
        status_msg = await message.reply_text("📤 Sending OTP...")
        success, msg_text = await session_mgr.start_phone_login(text)
        await status_msg.edit_text(f"{'✅' if success else '❌'} {msg_text}")
    
    elif state == SessionState.AWAITING_CODE:
        clean_code = text.replace(" ", "").replace("-", "").strip()
        status_msg = await message.reply_text("🔐 Verifying code...")
        success, msg_text = await session_mgr.verify_code(clean_code)
        await status_msg.edit_text(f"{'✅' if success else '❌'} {msg_text}")
    
    elif state == SessionState.AWAITING_PASSWORD:
        try:
            await message.delete()
        except Exception:
            pass
        status_msg = await client.send_message(message.chat.id, "🔐 Verifying 2FA...")
        success, msg_text = await session_mgr.verify_password(text)
        await status_msg.edit_text(f"{'✅' if success else '❌'} {msg_text}")


async def handle_telegram_link(client: Client, message: Message):
    """Handle link pasted in Channel, Group, or DM"""
    text = message.text or message.caption or ""
    matches = TG_LINK_PATTERN.findall(text)
    
    if not matches:
        return
    
    user_id = permissions.get_user_id(message)
    if not permissions.is_authorized(user_id):
        return

    # Delete the command / link message immediately
    dest_chat_id = message.chat.id
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Could not delete link message: {e}")

    if not session_mgr.is_logged_in:
        temp = await client.send_message(dest_chat_id, "❌ Userbot is not logged in! Send `/session <string>` in Bot DM.")
        await asyncio.sleep(5)
        await temp.delete()
        return

    for chat_ref, start_id_str, end_id_str in matches:
        try:
            start_id = int(start_id_str)
            end_id = int(end_id_str) if end_id_str else start_id
            
            # Resolve source chat ID
            if chat_ref.isdigit():
                source_id = int(f"-100{chat_ref}")
            else:
                try:
                    chat = await session_mgr.user_client.get_chat(chat_ref)
                    source_id = chat.id
                except Exception as e:
                    temp = await client.send_message(dest_chat_id, f"❌ Cannot access `{chat_ref}`: {e}")
                    await asyncio.sleep(5)
                    await temp.delete()
                    continue
            
            # Status placeholder
            status_msg = await client.send_message(dest_chat_id, f"⏳ Extracting {start_id} to {end_id}...")
            
            total_copied = 0
            for msg_id in range(start_id, end_id + 1):
                success, status_text, bytes_used = await copy_engine.copy_single_message(
                    user_client=session_mgr.user_client,
                    bot_client=client,
                    source_chat_id=source_id,
                    message_id=msg_id,
                    dest_chat_id=dest_chat_id,
                )
                if success:
                    total_copied += 1
                await asyncio.sleep(0.5)
            
            # Delete temporary processing message
            try:
                await status_msg.delete()
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Link copy error: {e}")


def register_message_handlers(app: Client):
    # Link handler (Handles channels, groups, and private chats)
    app.add_handler(
        MessageHandler(
            handle_telegram_link,
            filters.text & filters.regex(TG_LINK_PATTERN.pattern)
        ),
        group=1
    )
    
    # Private login inputs
    app.add_handler(
        MessageHandler(
            handle_login_input,
            filters.text & filters.private & ~filters.command([
                "start", "help", "status", "login", "session", "logout",
                "connect", "setdest", "disconnect", "analyze",
                "copy", "v", "p", "d", "a", "pause", "resume", "stop", "skip"
            ])
        ),
        group=2
    )
    
    logger.info("Message & Link handlers registered")
