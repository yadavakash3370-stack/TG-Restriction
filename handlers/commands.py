"""All bot command handlers"""
import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from config import OWNER_ID, BOT_SIGNATURE
from auth.permissions import (
    permissions,
    owner_only,
    admin_or_owner,
    any_authorized,
    Role,
)
from auth.session_manager import session_mgr, SessionState
from core.channel_manager import channel_mgr
from core.copy_engine import copy_engine
from core.bandwidth import bandwidth
from utils.logger import logger


# ==================== START & HELP ====================

@any_authorized
async def start_command(client: Client, message: Message):
    """Handle /start command"""
    role = permissions.get_role(message.from_user.id)
    
    text = (
        f"👋 **Welcome to Channel Copier Bot!**\n\n"
        f"🎭 Your role: **{role.value.upper()}**\n"
        f"🆔 Your ID: `{message.from_user.id}`\n\n"
        f"📌 Use /help to see available commands\n"
        f"📌 Use /status to check bot status\n\n"
        f"— {BOT_SIGNATURE}"
    )
    await message.reply_text(text)


async def help_command(client: Client, message: Message):
    """Handle /help - shows commands based on role"""
    user_id = message.from_user.id
    
    if not permissions.is_authorized(user_id):
        await message.reply_text(
            "🚫 **Access Denied!**\n\n"
            "This bot is for authorized users only."
        )
        return
    
    role = permissions.get_role(user_id)
    
    # Base commands (all authorized users)
    text = (
        "📚 **Available Commands**\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "**📊 Monitoring:**\n"
        "• /start - Welcome message\n"
        "• /help - This message\n"
        "• /status - Bot & connection status\n"
        "• /progress - Live copy progress\n"
        "• /speed - Current copy speed\n"
    )
    
    if role in (Role.OWNER, Role.ADMIN):
        text += (
            "\n**🔐 Authentication:**\n"
            "• /login - Login with phone + OTP\n"
            "• /session `<string>` - Login with session string\n"
            "• /logout - Logout\n"
            "\n**🔗 Channels:**\n"
            "• /connect - Connect source channel\n"
            "• /setdest - Set destination channel\n"
            "• /disconnect - Remove source\n"
            "• /analyze - Analyze source channel\n"
            "\n**📥 Copy:**\n"
            "• /copy `1-50` - Copy range (all types)\n"
            "• /copy all - Copy entire channel\n"
            "• /v `1-50` - Only videos\n"
            "• /p `1-50` - Only PDFs\n"
            "• /d `1-50` - Only documents\n"
            "• /a `1-50` - All content\n"
            "• Paste link - Copy single message\n"
            "\n**⏯ Control:**\n"
            "• /pause - Pause copy\n"
            "• /resume - Resume copy\n"
            "• /stop - Stop copy\n"
            "• /skip - Skip current\n"
            "\n**⚙️ Settings:**\n"
            "• /mode - Current mode\n"
            "• /limit `<gb>` - Set bandwidth limit\n"
            "• /reset - Reset bandwidth counter\n"
            "• /userlist - List authorized users\n"
        )
    
    if role == Role.OWNER:
        text += (
            "\n**👥 User Management (Owner):**\n"
            "• /adduser `<id>` - Add monitor user\n"
            "• /addadmin `<id>` - Add admin user\n"
            "• /removeuser `<id>` - Remove user\n"
            "• /removeadmin `<id>` - Remove admin\n"
            "• /broadcast `<msg>` - Message all users\n"
        )
    
    text += f"\n— {BOT_SIGNATURE}"
    await message.reply_text(text)


# ==================== STATUS COMMANDS ====================

@any_authorized
async def status_command(client: Client, message: Message):
    """Handle /status - shows overall bot status"""
    session_status = session_mgr.get_status()
    channel_status = channel_mgr.get_status()
    bandwidth_status = bandwidth.format_status()
    
    text = (
        f"🤖 **Bot Status Overview**\n\n"
        f"**Session:**\n{session_status}\n\n"
        f"{channel_status}\n\n"
        f"{bandwidth_status}"
    )
    await message.reply_text(text)


@any_authorized
async def progress_command(client: Client, message: Message):
    """Handle /progress - shows current copy progress"""
    if not copy_engine.is_running or not copy_engine.current_progress:
        await message.reply_text("ℹ️ No copy operation in progress.")
        return
    
    progress = copy_engine.current_progress
    text = (
        f"⏳ **Copy Progress**\n\n"
        f"{progress.format_summary()}\n\n"
        f"📄 Current: `{progress.current_file or 'N/A'}`"
    )
    if copy_engine.is_paused:
        text += "\n\n⏸ **PAUSED** - Use /resume"
    await message.reply_text(text)


@any_authorized
async def speed_command(client: Client, message: Message):
    """Handle /speed - shows current copy speed"""
    if not copy_engine.current_progress:
        await message.reply_text("ℹ️ No active copy operation.")
        return
    
    speed = copy_engine.current_progress.get_speed_mbps()
    await message.reply_text(f"⚡ **Current Speed:** `{speed:.2f} MB/s`")


# ==================== USER MANAGEMENT ====================

@owner_only
async def adduser_command(client: Client, message: Message):
    """Handle /adduser <id> - add monitor user"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("Usage: `/adduser <user_id>`")
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.reply_text("❌ Invalid user ID. Must be a number.")
        return
    
    name = "Unknown"
    try:
        user = await client.get_users(user_id)
        name = f"{user.first_name} {user.last_name or ''}".strip()
    except Exception:
        pass
    
    if permissions.add_user(user_id, name):
        await message.reply_text(
            f"✅ **User Added!**\n\n"
            f"👤 Name: {name}\n"
            f"🆔 ID: `{user_id}`\n"
            f"🔓 Access: **MONITOR ONLY**"
        )
    else:
        await message.reply_text("❌ User is already an admin or owner.")


@owner_only
async def addadmin_command(client: Client, message: Message):
    """Handle /addadmin <id> - add admin user"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("Usage: `/addadmin <user_id>`")
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.reply_text("❌ Invalid user ID.")
        return
    
    name = "Unknown"
    try:
        user = await client.get_users(user_id)
        name = f"{user.first_name} {user.last_name or ''}".strip()
    except Exception:
        pass
    
    if permissions.add_admin(user_id, name):
        await message.reply_text(
            f"✅ **Admin Added!**\n\n"
            f"👤 Name: {name}\n"
            f"🆔 ID: `{user_id}`\n"
            f"🔓 Access: **FULL** (except user management)"
        )
    else:
        await message.reply_text("❌ Cannot add owner as admin.")


@owner_only
async def removeuser_command(client: Client, message: Message):
    """Handle /removeuser <id>"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("Usage: `/removeuser <user_id>`")
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.reply_text("❌ Invalid user ID.")
        return
    
    if permissions.remove_user(user_id):
        await message.reply_text(f"🗑 User `{user_id}` removed.")
    else:
        await message.reply_text("❌ User not found in the list.")


@owner_only
async def removeadmin_command(client: Client, message: Message):
    """Handle /removeadmin <id>"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("Usage: `/removeadmin <user_id>`")
        return
    
    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.reply_text("❌ Invalid user ID.")
        return
    
    if permissions.remove_admin(user_id):
        await message.reply_text(f"🗑 Admin `{user_id}` removed.")
    else:
        await message.reply_text("❌ Admin not found.")


@admin_or_owner
async def userlist_command(client: Client, message: Message):
    """Handle /userlist"""
    text = "👥 **Authorized Users**\n━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"👑 **Owner:** `{OWNER_ID}`\n\n"
    
    if permissions.admins:
        text += f"🛡 **Admins ({len(permissions.admins)}):**\n"
        for uid, info in permissions.admins.items():
            text += f"  • {info['name']} - `{uid}`\n"
        text += "\n"
    else:
        text += "🛡 No admins added.\n\n"
    
    if permissions.users:
        text += f"👤 **Monitor Users ({len(permissions.users)}):**\n"
        for uid, info in permissions.users.items():
            text += f"  • {info['name']} - `{uid}`\n"
    else:
        text += "👤 No monitor users added."
    
    await message.reply_text(text)


@owner_only
async def broadcast_command(client: Client, message: Message):
    """Handle /broadcast <message>"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("Usage: `/broadcast <your message>`")
        return
    
    broadcast_text = f"📢 **Broadcast from Owner**\n\n{args[1]}"
    ids = permissions.get_all_authorized_ids()
    ids.discard(message.from_user.id)  # Don't send to self
    
    sent = 0
    failed = 0
    for uid in ids:
        try:
            await client.send_message(uid, broadcast_text)
            sent += 1
        except Exception as e:
            logger.warning(f"Broadcast to {uid} failed: {e}")
            failed += 1
    
    await message.reply_text(
        f"📢 **Broadcast Sent!**\n\n"
        f"✅ Delivered: {sent}\n"
        f"❌ Failed: {failed}"
    )


# ==================== AUTHENTICATION ====================

@admin_or_owner
async def login_command(client: Client, message: Message):
    """Handle /login - starts phone-based login"""
    if session_mgr.is_logged_in:
        await message.reply_text(
            "⚠️ Already logged in. Use /logout first."
        )
        return
    
    session_mgr.login_state = SessionState.AWAITING_PHONE
    await message.reply_text(
        "📱 **Phone Login**\n\n"
        "Send your phone number with country code.\n"
        "Example: `+919876543210`\n\n"
        "Type /cancel to abort."
    )


@admin_or_owner
async def session_command(client: Client, message: Message):
    """Handle /session <string> - login with session string"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text(
            "Usage: `/session <session_string>`\n\n"
            "Generate one using Pyrogram/Telethon session generators."
        )
        return
    
    session_string = args[1].strip()
    
    # Delete the message with session string for security
    try:
        await message.delete()
    except Exception:
        pass
    
    status_msg = await client.send_message(
        message.chat.id,
        "🔑 Verifying session string..."
    )
    
    success, msg_text = await session_mgr.login_with_session_string(session_string)
    
    if success:
        info = session_mgr.account_info
        await status_msg.edit_text(
            f"✅ **Login Successful!**\n\n"
            f"👤 Name: {info.get('name')}\n"
            f"🆔 ID: `{info.get('id')}`\n"
            f"📱 Phone: {info.get('phone', 'N/A')}\n\n"
            f"Now use /connect to link a source channel."
        )
    else:
        await status_msg.edit_text(f"❌ {msg_text}")


@admin_or_owner
async def logout_command(client: Client, message: Message):
    """Handle /logout"""
    success, msg_text = await session_mgr.logout()
    channel_mgr.clear_source()
    channel_mgr.clear_destination()
    await message.reply_text(f"{'✅' if success else '❌'} {msg_text}")


async def cancel_command(client: Client, message: Message):
    """Handle /cancel - cancel pending operations"""
    if session_mgr.login_state != SessionState.IDLE:
        session_mgr.login_state = SessionState.IDLE
        if session_mgr.temp_client:
            try:
                await session_mgr.temp_client.disconnect()
            except Exception:
                pass
            session_mgr.temp_client = None
        await message.reply_text("❌ Login process cancelled.")
        return
    
    if channel_mgr.pending_search_results:
        channel_mgr.pending_search_results = []
        channel_mgr.pending_search_type = None
        await message.reply_text("❌ Channel selection cancelled.")
        return
    
    await message.reply_text("Nothing to cancel.")


# ==================== CHANNEL COMMANDS ====================

@admin_or_owner
async def connect_command(client: Client, message: Message):
    """Handle /connect - search & connect source channel"""
    if not session_mgr.is_logged_in:
        await message.reply_text(
            "❌ Please /login or /session first."
        )
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text(
            "Usage: `/connect <channel_name_or_username>`\n\n"
            "Examples:\n"
            "• `/connect Tech Videos`\n"
            "• `/connect @techvideos`\n"
            "• `/connect https://t.me/techvideos`"
        )
        return
    
    query = args[1].strip()
    status_msg = await message.reply_text(f"🔍 Searching for: `{query}`...")
    
    try:
        results = await channel_mgr.search_channels(session_mgr.user_client, query)
    except Exception as e:
        await status_msg.edit_text(f"❌ Search error: {e}")
        return
    
    if not results:
        await status_msg.edit_text(
            "❌ No channels found.\n\n"
            "Make sure you're a member of the channel, or try the @username."
        )
        return
    
    if len(results) == 1:
        chat = results[0]
        channel_mgr.set_source(chat)
        await status_msg.edit_text(
            f"✅ **Source Connected!**\n\n"
            f"📥 {chat.title}\n"
            f"🆔 `{chat.id}`\n"
            f"{'🔗 @' + chat.username if chat.username else ''}\n\n"
            f"Use /analyze to scan content."
        )
        return
    
    # Multiple results - let user choose
    channel_mgr.pending_search_results = results
    channel_mgr.pending_search_type = "source"
    
    text = "🔎 **Multiple channels found. Choose one:**\n\n"
    for i, chat in enumerate(results, 1):
        username = f"@{chat.username}" if chat.username else "private"
        text += f"{i}. **{chat.title}** ({username})\n"
    text += "\nReply with the number (1-{}) or /cancel".format(len(results))
    
    await status_msg.edit_text(text)


@admin_or_owner
async def setdest_command(client: Client, message: Message):
    """Handle /setdest - set destination channel"""
    if not session_mgr.is_logged_in:
        await message.reply_text("❌ Please /login or /session first.")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text(
            "Usage: `/setdest <channel_name_or_username>`"
        )
        return
    
    query = args[1].strip()
    status_msg = await message.reply_text(f"🔍 Searching for: `{query}`...")
    
    try:
        results = await channel_mgr.search_channels(session_mgr.user_client, query)
    except Exception as e:
        await status_msg.edit_text(f"❌ Search error: {e}")
        return
    
    if not results:
        await status_msg.edit_text("❌ No channels found.")
        return
    
    if len(results) == 1:
        chat = results[0]
        channel_mgr.set_destination(chat)
        await status_msg.edit_text(
            f"✅ **Destination Set!**\n\n"
            f"📤 {chat.title}\n"
            f"🆔 `{chat.id}`"
        )
        return
    
    channel_mgr.pending_search_results = results
    channel_mgr.pending_search_type = "destination"
    
    text = "🔎 **Multiple channels found. Choose one:**\n\n"
    for i, chat in enumerate(results, 1):
        username = f"@{chat.username}" if chat.username else "private"
        text += f"{i}. **{chat.title}** ({username})\n"
    text += f"\nReply with the number (1-{len(results)}) or /cancel"
    
    await status_msg.edit_text(text)


@admin_or_owner
async def disconnect_command(client: Client, message: Message):
    """Handle /disconnect"""
    channel_mgr.clear_source()
    await message.reply_text("✅ Source channel disconnected.")


@admin_or_owner
async def analyze_command(client: Client, message: Message):
    """Handle /analyze - analyze source channel"""
    if not session_mgr.is_logged_in:
        await message.reply_text("❌ Please login first.")
        return
    
    if not channel_mgr.source_chat:
        await message.reply_text("❌ No source channel. Use /connect first.")
        return
    
    status_msg = await message.reply_text("📊 Analyzing channel... please wait...")
    
    try:
        analysis = await channel_mgr.analyze_channel(
            session_mgr.user_client, limit=1000
        )
        await status_msg.edit_text(channel_mgr.format_analysis(analysis))
    except Exception as e:
        await status_msg.edit_text(f"❌ Analysis failed: {e}")


# ==================== COPY COMMANDS ====================

def parse_range(args_text: str) -> tuple[int, int, bool]:
    """
    Parse range like '1-50' or 'all'.
    Returns (start, end, is_all)
    """
    args_text = args_text.strip().lower()
    if args_text == "all":
        return 0, 0, True
    
    match = re.match(r"^(\d+)\s*-\s*(\d+)$", args_text)
    if match:
        return int(match.group(1)), int(match.group(2)), False
    
    # Single number = just that one
    match = re.match(r"^(\d+)$", args_text)
    if match:
        n = int(match.group(1))
        return n, n, False
    
    raise ValueError("Invalid range format")


async def _copy_handler(
    client: Client,
    message: Message,
    filter_type: str,
):
    """Common copy handler used by /copy, /v, /p, /d, /a"""
    if not session_mgr.is_logged_in:
        await message.reply_text("❌ Please login first.")
        return
    
    if not channel_mgr.source_chat:
        await message.reply_text("❌ No source channel. Use /connect first.")
        return
    
    if not channel_mgr.destination_chat:
        await message.reply_text("❌ No destination set. Use /setdest first.")
        return
    
    if copy_engine.is_running:
        await message.reply_text(
            "⚠️ A copy operation is already running.\n"
            "Use /stop first or wait for it to complete."
        )
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text(
            f"Usage: `{message.command[0]} <range>`\n\n"
            f"Examples:\n"
            f"• `/{message.command[0]} 1-50`\n"
            f"• `/{message.command[0]} all`\n"
            f"• `/{message.command[0]} 25` (single message)"
        )
        return
    
    try:
        start, end, is_all = parse_range(args[1])
    except ValueError:
        await message.reply_text("❌ Invalid range. Use `1-50` or `all`.")
        return
    
    status_msg = await message.reply_text("🚀 Starting copy operation...")
    
    try:
        if is_all:
            progress = await copy_engine.copy_all(
                user_client=session_mgr.user_client,
                bot_client=client,
                source_chat_id=channel_mgr.source_chat.id,
                dest_chat_id=channel_mgr.destination_chat.id,
                filter_type=filter_type,
                status_message=status_msg,
            )
        else:
            progress = await copy_engine.copy_range(
                user_client=session_mgr.user_client,
                bot_client=client,
                source_chat_id=channel_mgr.source_chat.id,
                dest_chat_id=channel_mgr.destination_chat.id,
                start_id=start,
                end_id=end,
                filter_type=filter_type,
                status_message=status_msg,
            )
        
        # Final summary
        final_text = (
            f"{'🛑' if copy_engine.is_stopped else '✅'} **Copy Complete!**\n\n"
            f"{progress.format_summary()}\n\n"
            f"📊 {bandwidth.format_status()}"
        )
        await status_msg.edit_text(final_text)
    
    except Exception as e:
        logger.error(f"Copy operation error: {e}")
        await status_msg.edit_text(f"❌ Copy failed: {e}")


@admin_or_owner
async def copy_command(client: Client, message: Message):
    await _copy_handler(client, message, "all")


@admin_or_owner
async def v_command(client: Client, message: Message):
    await _copy_handler(client, message, "video")


@admin_or_owner
async def p_command(client: Client, message: Message):
    await _copy_handler(client, message, "pdf")


@admin_or_owner
async def d_command(client: Client, message: Message):
    await _copy_handler(client, message, "document")


@admin_or_owner
async def a_command(client: Client, message: Message):
    await _copy_handler(client, message, "all")


# ==================== CONTROL COMMANDS ====================

@admin_or_owner
async def pause_command(client: Client, message: Message):
    if not copy_engine.is_running:
        await message.reply_text("ℹ️ No active copy operation.")
        return
    copy_engine.pause()
    await message.reply_text("⏸ Copy paused. Use /resume to continue.")


@admin_or_owner
async def resume_command(client: Client, message: Message):
    if not copy_engine.is_running:
        await message.reply_text("ℹ️ No active copy operation.")
        return
    copy_engine.resume()
    await message.reply_text("▶️ Copy resumed.")


@admin_or_owner
async def stop_command(client: Client, message: Message):
    if not copy_engine.is_running:
        await message.reply_text("ℹ️ No active copy operation.")
        return
    copy_engine.stop()
    await message.reply_text("🛑 Copy stopping...")


@admin_or_owner
async def skip_command(client: Client, message: Message):
    if not copy_engine.is_running:
        await message.reply_text("ℹ️ No active copy operation.")
        return
    copy_engine.skip()
    await message.reply_text("⏭ Skipping current file...")


# ==================== SETTINGS COMMANDS ====================

@admin_or_owner
async def mode_command(client: Client, message: Message):
    mode = bandwidth.get_mode()
    await message.reply_text(
        f"⚙️ **Current Mode:** {mode}\n\n"
        f"{bandwidth.format_status()}"
    )


@admin_or_owner
async def limit_command(client: Client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text(
            f"Usage: `/limit <gb>`\n"
            f"Current: `{bandwidth.limit_gb} GB`"
        )
        return
    
    try:
        gb = float(args[1].strip())
        if gb <= 0:
            raise ValueError()
        bandwidth.set_limit(gb)
        await message.reply_text(f"✅ Bandwidth limit set to `{gb} GB`.")
    except ValueError:
        await message.reply_text("❌ Invalid value. Use a positive number.")


@admin_or_owner
async def reset_command(client: Client, message: Message):
    bandwidth.reset()
    await message.reply_text("✅ Bandwidth counter reset to 0.")


# ==================== HANDLER REGISTRATION ====================

def register_command_handlers(app: Client):
    """Register all command handlers with the bot"""
    
    # Basic
    app.add_handler(
        __import__("pyrogram.handlers", fromlist=["MessageHandler"])
        .MessageHandler(start_command, filters.command("start") & filters.private)
    )
    
    from pyrogram.handlers import MessageHandler
    
    # Basic commands
    app.add_handler(MessageHandler(start_command, filters.command("start")))
    app.add_handler(MessageHandler(help_command, filters.command("help")))
    app.add_handler(MessageHandler(cancel_command, filters.command("cancel")))
    
    # Status
    app.add_handler(MessageHandler(status_command, filters.command("status")))
    app.add_handler(MessageHandler(progress_command, filters.command("progress")))
    app.add_handler(MessageHandler(speed_command, filters.command("speed")))
    
    # User management (owner)
    app.add_handler(MessageHandler(adduser_command, filters.command("adduser")))
    app.add_handler(MessageHandler(addadmin_command, filters.command("addadmin")))
    app.add_handler(MessageHandler(removeuser_command, filters.command("removeuser")))
    app.add_handler(MessageHandler(removeadmin_command, filters.command("removeadmin")))
    app.add_handler(MessageHandler(userlist_command, filters.command("userlist")))
    app.add_handler(MessageHandler(broadcast_command, filters.command("broadcast")))
    
    # Auth
    app.add_handler(MessageHandler(login_command, filters.command("login")))
    app.add_handler(MessageHandler(session_command, filters.command("session")))
    app.add_handler(MessageHandler(logout_command, filters.command("logout")))
    
    # Channels
    app.add_handler(MessageHandler(connect_command, filters.command("connect")))
    app.add_handler(MessageHandler(setdest_command, filters.command("setdest")))
    app.add_handler(MessageHandler(disconnect_command, filters.command("disconnect")))
    app.add_handler(MessageHandler(analyze_command, filters.command("analyze")))
    
    # Copy
    app.add_handler(MessageHandler(copy_command, filters.command("copy")))
    app.add_handler(MessageHandler(v_command, filters.command("v")))
    app.add_handler(MessageHandler(p_command, filters.command("p")))
    app.add_handler(MessageHandler(d_command, filters.command("d")))
    app.add_handler(MessageHandler(a_command, filters.command("a")))
    
    # Control
    app.add_handler(MessageHandler(pause_command, filters.command("pause")))
    app.add_handler(MessageHandler(resume_command, filters.command("resume")))
    app.add_handler(MessageHandler(stop_command, filters.command("stop")))
    app.add_handler(MessageHandler(skip_command, filters.command("skip")))
    
    # Settings
    app.add_handler(MessageHandler(mode_command, filters.command("mode")))
    app.add_handler(MessageHandler(limit_command, filters.command("limit")))
    app.add_handler(MessageHandler(reset_command, filters.command("reset")))
    
    logger.info("All command handlers registered")
