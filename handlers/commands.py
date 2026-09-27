"""All bot command handlers - Channel & Group compatible with auto-delete"""
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.handlers import MessageHandler
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


# ==================== HELPER ====================

async def safe_delete(message: Message):
    """Safely delete a message (works in channels too)"""
    try:
        await message.delete()
    except Exception:
        pass


async def temp_reply(client: Client, chat_id: int, text: str, delete_after: int = 8):
    """Send a temporary message that auto-deletes"""
    try:
        msg = await client.send_message(chat_id, text)
        await asyncio.sleep(delete_after)
        await msg.delete()
    except Exception:
        pass


def get_sender_id(message: Message) -> int:
    """Get sender ID safely (works in channels where from_user is None)"""
    if message.from_user:
        return message.from_user.id
    if message.sender_chat:
        return message.sender_chat.id
    return 0


# ==================== START & HELP ====================

@any_authorized
async def start_command(client: Client, message: Message):
    await safe_delete(message)
    role = permissions.get_role(get_sender_id(message))
    text = (
        f"👋 **Channel Copier Bot Active!**\n\n"
        f"🎭 Role: **{role.value.upper()}**\n"
        f"📌 /help for commands\n"
        f"📌 /status for bot status\n\n"
        f"— {BOT_SIGNATURE}"
    )
    await temp_reply(client, message.chat.id, text, delete_after=15)


@any_authorized
async def help_command(client: Client, message: Message):
    await safe_delete(message)
    user_id = get_sender_id(message)
    role = permissions.get_role(user_id)

    text = (
        "📚 **Commands**\n"
        "━━━━━━━━━━━━━━━\n\n"
        "**📊 Monitoring:**\n"
        "• /status - Bot status\n"
        "• /progress - Copy progress\n"
        "• /speed - Copy speed\n"
    )

    if role in (Role.OWNER, Role.ADMIN):
        text += (
            "\n**🔐 Auth (Use in Bot DM):**\n"
            "• /login - Phone + OTP\n"
            "• /session `<string>` - Session login\n"
            "• /logout - Logout\n"
            "\n**🔗 Channels:**\n"
            "• /connect `<name>` - Source channel\n"
            "• /setdest `<name>` - Destination\n"
            "• /disconnect - Remove source\n"
            "• /analyze - Scan source\n"
            "\n**📥 Copy:**\n"
            "• /copy `1-50` - All types\n"
            "• /copy all - Entire channel\n"
            "• /v `1-50` - Videos only\n"
            "• /p `1-50` - PDFs only\n"
            "• /d `1-50` - Documents only\n"
            "• Paste link - Auto copy\n"
            "\n**⏯ Control:**\n"
            "• /pause /resume /stop /skip\n"
            "\n**⚙️ Settings:**\n"
            "• /mode - Current mode\n"
            "• /limit `<gb>` - BW limit\n"
            "• /reset - Reset BW counter\n"
        )

    if role == Role.OWNER:
        text += (
            "\n**👥 User Mgmt (Owner):**\n"
            "• /adduser `<id>`\n"
            "• /addadmin `<id>`\n"
            "• /removeuser `<id>`\n"
            "• /removeadmin `<id>`\n"
            "• /userlist\n"
            "• /broadcast `<msg>`\n"
        )

    text += f"\n— {BOT_SIGNATURE}"
    await temp_reply(client, message.chat.id, text, delete_after=30)


# ==================== STATUS ====================

@any_authorized
async def status_command(client: Client, message: Message):
    await safe_delete(message)
    session_status = session_mgr.get_status()
    channel_status = channel_mgr.get_status()
    bw_status = bandwidth.format_status()
    text = (
        f"🤖 **Bot Status**\n\n"
        f"**Session:**\n{session_status}\n\n"
        f"{channel_status}\n\n"
        f"{bw_status}"
    )
    await temp_reply(client, message.chat.id, text, delete_after=20)


@any_authorized
async def progress_command(client: Client, message: Message):
    await safe_delete(message)
    if not copy_engine.is_running or not copy_engine.current_progress:
        await temp_reply(client, message.chat.id, "ℹ️ No copy in progress.", 5)
        return
    p = copy_engine.current_progress
    text = f"⏳ **Progress**\n\n{p.format_summary()}"
    if copy_engine.is_paused:
        text += "\n\n⏸ **PAUSED**"
    await temp_reply(client, message.chat.id, text, 10)


@any_authorized
async def speed_command(client: Client, message: Message):
    await safe_delete(message)
    if not copy_engine.current_progress:
        await temp_reply(client, message.chat.id, "ℹ️ No active copy.", 5)
        return
    speed = copy_engine.current_progress.get_speed_mbps()
    await temp_reply(client, message.chat.id, f"⚡ Speed: `{speed:.2f} MB/s`", 5)


# ==================== USER MANAGEMENT (Owner Only) ====================

@owner_only
async def adduser_command(client: Client, message: Message):
    await safe_delete(message)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await temp_reply(client, message.chat.id, "Usage: `/adduser <id>`", 5)
        return
    try:
        uid = int(args[1].strip())
    except ValueError:
        await temp_reply(client, message.chat.id, "❌ Invalid ID.", 5)
        return
    name = "Unknown"
    try:
        u = await client.get_users(uid)
        name = f"{u.first_name} {u.last_name or ''}".strip()
    except Exception:
        pass
    if permissions.add_user(uid, name):
        await temp_reply(client, message.chat.id,
            f"✅ User added: {name} (`{uid}`)\n🔓 Monitor only", 8)
    else:
        await temp_reply(client, message.chat.id, "❌ Already admin/owner.", 5)


@owner_only
async def addadmin_command(client: Client, message: Message):
    await safe_delete(message)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await temp_reply(client, message.chat.id, "Usage: `/addadmin <id>`", 5)
        return
    try:
        uid = int(args[1].strip())
    except ValueError:
        await temp_reply(client, message.chat.id, "❌ Invalid ID.", 5)
        return
    name = "Unknown"
    try:
        u = await client.get_users(uid)
        name = f"{u.first_name} {u.last_name or ''}".strip()
    except Exception:
        pass
    if permissions.add_admin(uid, name):
        await temp_reply(client, message.chat.id,
            f"✅ Admin added: {name} (`{uid}`)\n🔓 Full access", 8)
    else:
        await temp_reply(client, message.chat.id, "❌ Cannot add owner.", 5)


@owner_only
async def removeuser_command(client: Client, message: Message):
    await safe_delete(message)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return
    try:
        uid = int(args[1].strip())
    except ValueError:
        return
    if permissions.remove_user(uid):
        await temp_reply(client, message.chat.id, f"🗑 User `{uid}` removed.", 5)
    else:
        await temp_reply(client, message.chat.id, "❌ Not found.", 5)


@owner_only
async def removeadmin_command(client: Client, message: Message):
    await safe_delete(message)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return
    try:
        uid = int(args[1].strip())
    except ValueError:
        return
    if permissions.remove_admin(uid):
        await temp_reply(client, message.chat.id, f"🗑 Admin `{uid}` removed.", 5)
    else:
        await temp_reply(client, message.chat.id, "❌ Not found.", 5)


@admin_or_owner
async def userlist_command(client: Client, message: Message):
    await safe_delete(message)
    text = f"👥 **Users**\n\n👑 Owner: `{OWNER_ID}`\n\n"
    if permissions.admins:
        text += f"🛡 Admins ({len(permissions.admins)}):\n"
        for uid, info in permissions.admins.items():
            text += f"  • {info['name']} - `{uid}`\n"
        text += "\n"
    if permissions.users:
        text += f"👤 Users ({len(permissions.users)}):\n"
        for uid, info in permissions.users.items():
            text += f"  • {info['name']} - `{uid}`\n"
    await temp_reply(client, message.chat.id, text, 15)


@owner_only
async def broadcast_command(client: Client, message: Message):
    await safe_delete(message)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await temp_reply(client, message.chat.id, "Usage: `/broadcast <msg>`", 5)
        return
    btext = f"📢 **Broadcast**\n\n{args[1]}"
    ids = permissions.get_all_authorized_ids()
    sent = failed = 0
    for uid in ids:
        try:
            await client.send_message(uid, btext)
            sent += 1
        except Exception:
            failed += 1
    await temp_reply(client, message.chat.id,
        f"📢 Sent: {sent} | Failed: {failed}", 8)
    # ==================== AUTH (Best used in Bot DM) ====================

@admin_or_owner
async def login_command(client: Client, message: Message):
    await safe_delete(message)
    if session_mgr.is_logged_in:
        await temp_reply(client, message.chat.id, "⚠️ Already logged in. /logout first.", 5)
        return
    session_mgr.login_state = SessionState.AWAITING_PHONE
    await temp_reply(client, message.chat.id,
        "📱 Send phone number: `+919876543210`\n/cancel to abort.", 15)


@admin_or_owner
async def session_command(client: Client, message: Message):
    await safe_delete(message)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await temp_reply(client, message.chat.id,
            "Usage: `/session <string>`", 8)
        return
    session_string = args[1].strip()
    status_msg = await client.send_message(message.chat.id, "🔑 Verifying...")
    success, msg_text = await session_mgr.login_with_session_string(session_string)
    if success:
        info = session_mgr.account_info
        await status_msg.edit_text(
            f"✅ **Logged in!**\n👤 {info.get('name')}\n"
            f"📱 {info.get('phone', 'N/A')}\n\n"
            f"Now paste links or use /connect"
        )
    else:
        await status_msg.edit_text(f"❌ {msg_text}")
    await asyncio.sleep(10)
    try:
        await status_msg.delete()
    except Exception:
        pass


@admin_or_owner
async def logout_command(client: Client, message: Message):
    await safe_delete(message)
    success, msg_text = await session_mgr.logout()
    channel_mgr.clear_source()
    channel_mgr.clear_destination()
    await temp_reply(client, message.chat.id,
        f"{'✅' if success else '❌'} {msg_text}", 5)


async def cancel_command(client: Client, message: Message):
    await safe_delete(message)
    if session_mgr.login_state != SessionState.IDLE:
        session_mgr.login_state = SessionState.IDLE
        if session_mgr.temp_client:
            try:
                await session_mgr.temp_client.disconnect()
            except Exception:
                pass
        await temp_reply(client, message.chat.id, "❌ Cancelled.", 5)
        return
    if channel_mgr.pending_search_results:
        channel_mgr.pending_search_results = []
        channel_mgr.pending_search_type = None
        await temp_reply(client, message.chat.id, "❌ Cancelled.", 5)
        return


# ==================== CHANNEL COMMANDS ====================

@admin_or_owner
async def connect_command(client: Client, message: Message):
    await safe_delete(message)
    if not session_mgr.is_logged_in:
        await temp_reply(client, message.chat.id, "❌ Login first: /session", 5)
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await temp_reply(client, message.chat.id,
            "Usage: `/connect <name or @username>`", 8)
        return
    query = args[1].strip()
    status_msg = await client.send_message(message.chat.id, f"🔍 Searching `{query}`...")
    try:
        results = await channel_mgr.search_channels(session_mgr.user_client, query)
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")
        await asyncio.sleep(5)
        await status_msg.delete()
        return
    if not results:
        await status_msg.edit_text("❌ No channels found.")
        await asyncio.sleep(5)
        await status_msg.delete()
        return
    if len(results) == 1:
        chat = results[0]
        channel_mgr.set_source(chat)
        await status_msg.edit_text(
            f"✅ **Source:** {chat.title}\n🆔 `{chat.id}`\nUse /analyze"
        )
        await asyncio.sleep(8)
        await status_msg.delete()
        return
    # Multiple results
    channel_mgr.pending_search_results = results
    channel_mgr.pending_search_type = "source"
    text = "🔎 **Choose source:**\n\n"
    for i, c in enumerate(results, 1):
        u = f"@{c.username}" if c.username else "private"
        text += f"{i}. **{c.title}** ({u})\n"
    text += f"\nReply with number (1-{len(results)})"
    await status_msg.edit_text(text)


@admin_or_owner
async def setdest_command(client: Client, message: Message):
    await safe_delete(message)
    if not session_mgr.is_logged_in:
        await temp_reply(client, message.chat.id, "❌ Login first.", 5)
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await temp_reply(client, message.chat.id, "Usage: `/setdest <name>`", 5)
        return
    query = args[1].strip()
    status_msg = await client.send_message(message.chat.id, f"🔍 Searching `{query}`...")
    try:
        results = await channel_mgr.search_channels(session_mgr.user_client, query)
    except Exception as e:
        await status_msg.edit_text(f"❌ {e}")
        await asyncio.sleep(5)
        await status_msg.delete()
        return
    if not results:
        await status_msg.edit_text("❌ Not found.")
        await asyncio.sleep(5)
        await status_msg.delete()
        return
    if len(results) == 1:
        channel_mgr.set_destination(results[0])
        await status_msg.edit_text(f"✅ **Dest:** {results[0].title}")
        await asyncio.sleep(5)
        await status_msg.delete()
        return
    channel_mgr.pending_search_results = results
    channel_mgr.pending_search_type = "destination"
    text = "🔎 **Choose destination:**\n\n"
    for i, c in enumerate(results, 1):
        u = f"@{c.username}" if c.username else "private"
        text += f"{i}. **{c.title}** ({u})\n"
    text += f"\nReply with number (1-{len(results)})"
    await status_msg.edit_text(text)


@admin_or_owner
async def disconnect_command(client: Client, message: Message):
    await safe_delete(message)
    channel_mgr.clear_source()
    await temp_reply(client, message.chat.id, "✅ Source disconnected.", 5)


@admin_or_owner
async def analyze_command(client: Client, message: Message):
    await safe_delete(message)
    if not session_mgr.is_logged_in:
        await temp_reply(client, message.chat.id, "❌ Login first.", 5)
        return
    if not channel_mgr.source_chat:
        await temp_reply(client, message.chat.id, "❌ /connect first.", 5)
        return
    status_msg = await client.send_message(message.chat.id, "📊 Analyzing...")
    try:
        analysis = await channel_mgr.analyze_channel(session_mgr.user_client, limit=1000)
        await status_msg.edit_text(channel_mgr.format_analysis(analysis))
    except Exception as e:
        await status_msg.edit_text(f"❌ {e}")


# ==================== COPY COMMANDS ====================

def parse_range(args_text: str) -> tuple:
    args_text = args_text.strip().lower()
    if args_text == "all":
        return 0, 0, True
    match = re.match(r"^(\d+)\s*-\s*(\d+)$", args_text)
    if match:
        return int(match.group(1)), int(match.group(2)), False
    match = re.match(r"^(\d+)$", args_text)
    if match:
        n = int(match.group(1))
        return n, n, False
    raise ValueError("Invalid range")


async def _copy_handler(client: Client, message: Message, filter_type: str):
    """Core copy logic - posts to SAME chat, deletes command"""
    dest_chat_id = message.chat.id
    await safe_delete(message)

    if not session_mgr.is_logged_in:
        await temp_reply(client, dest_chat_id, "❌ Login first: /session", 5)
        return

    if not channel_mgr.source_chat:
        await temp_reply(client, dest_chat_id,
            "❌ No source. Use /connect or paste direct links.", 5)
        return

    if copy_engine.is_running:
        await temp_reply(client, dest_chat_id, "⚠️ Copy already running.", 5)
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await temp_reply(client, dest_chat_id,
            f"Usage: `/{message.command[0]} 1-50` or `all`", 5)
        return

    try:
        start, end, is_all = parse_range(args[1])
    except ValueError:
        await temp_reply(client, dest_chat_id, "❌ Use `1-50` or `all`", 5)
        return

    status_msg = await client.send_message(dest_chat_id, "🚀 Starting copy...")

    try:
        if is_all:
            progress = await copy_engine.copy_all(
                user_client=session_mgr.user_client,
                bot_client=client,
                source_chat_id=channel_mgr.source_chat.id,
                dest_chat_id=dest_chat_id,
                filter_type=filter_type,
                status_message=status_msg,
            )
        else:
            progress = await copy_engine.copy_range(
                user_client=session_mgr.user_client,
                bot_client=client,
                source_chat_id=channel_mgr.source_chat.id,
                dest_chat_id=dest_chat_id,
                start_id=start,
                end_id=end,
                filter_type=filter_type,
                status_message=status_msg,
            )

        final = (
            f"{'🛑' if copy_engine.is_stopped else '✅'} **Done!**\n\n"
            f"{progress.format_summary()}"
        )
        try:
            await status_msg.edit_text(final)
            await asyncio.sleep(10)
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Copy error: {e}")
        try:
            await status_msg.edit_text(f"❌ {e}")
            await asyncio.sleep(8)
            await status_msg.delete()
        except Exception:
            pass


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


# ==================== CONTROL ====================

@admin_or_owner
async def pause_command(client: Client, message: Message):
    await safe_delete(message)
    if not copy_engine.is_running:
        return
    copy_engine.pause()
    await temp_reply(client, message.chat.id, "⏸ Paused. /resume", 5)

@admin_or_owner
async def resume_command(client: Client, message: Message):
    await safe_delete(message)
    if not copy_engine.is_running:
        return
    copy_engine.resume()
    await temp_reply(client, message.chat.id, "▶️ Resumed.", 5)

@admin_or_owner
async def stop_command(client: Client, message: Message):
    await safe_delete(message)
    if not copy_engine.is_running:
        return
    copy_engine.stop()
    await temp_reply(client, message.chat.id, "🛑 Stopping...", 5)

@admin_or_owner
async def skip_command(client: Client, message: Message):
    await safe_delete(message)
    if not copy_engine.is_running:
        return
    copy_engine.skip()
    await temp_reply(client, message.chat.id, "⏭ Skipped.", 3)


# ==================== SETTINGS ====================

@admin_or_owner
async def mode_command(client: Client, message: Message):
    await safe_delete(message)
    await temp_reply(client, message.chat.id,
        f"⚙️ Mode: {bandwidth.get_mode()}\n\n{bandwidth.format_status()}", 10)

@admin_or_owner
async def limit_command(client: Client, message: Message):
    await safe_delete(message)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await temp_reply(client, message.chat.id,
            f"Usage: `/limit <gb>` | Current: `{bandwidth.limit_gb} GB`", 5)
        return
    try:
        gb = float(args[1].strip())
        if gb <= 0:
            raise ValueError()
        bandwidth.set_limit(gb)
        await temp_reply(client, message.chat.id, f"✅ Limit: `{gb} GB`", 5)
    except ValueError:
        await temp_reply(client, message.chat.id, "❌ Invalid number.", 5)

@admin_or_owner
async def reset_command(client: Client, message: Message):
    await safe_delete(message)
    bandwidth.reset()
    await temp_reply(client, message.chat.id, "✅ BW counter reset.", 5)


# ==================== REGISTER ALL ====================

def register_command_handlers(app: Client):
    """Register all command handlers"""

    # Basic
    app.add_handler(MessageHandler(start_command, filters.command("start")))
    app.add_handler(MessageHandler(help_command, filters.command("help")))
    app.add_handler(MessageHandler(cancel_command, filters.command("cancel")))

    # Status
    app.add_handler(MessageHandler(status_command, filters.command("status")))
    app.add_handler(MessageHandler(progress_command, filters.command("progress")))
    app.add_handler(MessageHandler(speed_command, filters.command("speed")))

    # User management
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
