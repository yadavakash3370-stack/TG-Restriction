"""Message handlers - STRICT destination check (Never dumps to Saved Messages)"""
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler
from auth.permissions import permissions
from auth.session_manager import session_mgr, SessionState
from core.channel_manager import channel_mgr
from core.copy_engine import copy_engine
from utils.logger import logger

TG_LINK_PATTERN = re.compile(
    r"https?://t\.me/(?:c/)?([\w\d_]+)/(\d+)(?:-(\d+))?"
)


async def handle_login_input(client: Client, message: Message):
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
            await message.reply_text("❌ Format: `+919876543210`")
            return
        s = await message.reply_text("📤 Sending OTP...")
        ok, msg = await session_mgr.start_phone_login(text)
        await s.edit_text(f"{'✅' if ok else '❌'} {msg}")
    elif state == SessionState.AWAITING_CODE:
        code = text.replace(" ", "").replace("-", "")
        s = await message.reply_text("🔐 Verifying...")
        ok, msg = await session_mgr.verify_code(code)
        await s.edit_text(f"{'✅' if ok else '❌'} {msg}")
    elif state == SessionState.AWAITING_PASSWORD:
        try:
            await message.delete()
        except Exception:
            pass
        s = await client.send_message(message.chat.id, "🔐 Checking 2FA...")
        ok, msg = await session_mgr.verify_password(text)
        await s.edit_text(f"{'✅' if ok else '❌'} {msg}")


async def handle_telegram_link(client: Client, message: Message):
    """Link paste handler - strictly sends to Destination Channel"""
    text = message.text or message.caption or ""
    matches = TG_LINK_PATTERN.findall(text)
    if not matches:
        return

    user_id = permissions.get_user_id(message)
    if not permissions.is_authorized(user_id):
        return

    # Delete the user's link message
    try:
        await message.delete()
    except Exception:
        pass

    # Destination resolution:
    # 1. If posted directly in a Channel/Supergroup, destination IS that chat.
    # 2. If posted in Bot DM, destination MUST be channel_mgr.get_destination_id()
    if message.chat.type.name in ("CHANNEL", "SUPERGROUP"):
        dest_chat_id = message.chat.id
    else:
        dest_chat_id = channel_mgr.get_destination_id()

    # STRICT CHECK: Do not allow sending to a user ID / Saved Messages
    if not dest_chat_id or (isinstance(dest_chat_id, int) and dest_chat_id > 0):
        temp = await client.send_message(
            message.chat.id,
            "❌ **Destination Channel is not set!**\n\n"
            "Please use `/setdest @yourchannel` or set `DESTINATION_CHANNEL` in Render environment variables.\n"
            "(Bot cannot dump files into Saved Messages)"
        )
        await asyncio.sleep(8)
        try:
            await temp.delete()
        except Exception:
            pass
        return

    if not session_mgr.is_logged_in:
        temp = await client.send_message(message.chat.id, "❌ Not logged in! Use /session in DM.")
        await asyncio.sleep(6)
        try:
            await temp.delete()
        except Exception:
            pass
        return

    for chat_ref, start_str, end_str in matches:
        try:
            start_id = int(start_str)
            end_id = int(end_str) if end_str else start_id

            if chat_ref.isdigit():
                source_id = int(f"-100{chat_ref}")
            else:
                try:
                    chat = await session_mgr.user_client.get_chat(chat_ref)
                    source_id = chat.id
                except Exception as e:
                    temp = await client.send_message(message.chat.id, f"❌ Can't access source `{chat_ref}`: {e}")
                    await asyncio.sleep(6)
                    try:
                        await temp.delete()
                    except Exception:
                        pass
                    continue

            status_msg = await client.send_message(
                dest_chat_id, f"⏳ Extracting {start_id} to {end_id}..."
            )

            copied = 0
            for msg_id in range(start_id, end_id + 1):
                success, status_text, _ = await copy_engine.copy_single_message(
                    user_client=session_mgr.user_client,
                    source_chat_id=source_id,
                    message_id=msg_id,
                    dest_chat_id=dest_chat_id,
                )
                if success:
                    copied += 1
                await asyncio.sleep(0.5)

            try:
                await status_msg.edit_text(f"✅ Extraction completed! ({copied} items)")
                await asyncio.sleep(5)
                await status_msg.delete()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Link copy error: {e}")


def register_message_handlers(app: Client):
    app.add_handler(
        MessageHandler(
            handle_telegram_link,
            filters.text & filters.regex(TG_LINK_PATTERN.pattern)
        ),
        group=1
    )
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
            ])
        ),
        group=2
    )
    logger.info("Message handlers registered")
