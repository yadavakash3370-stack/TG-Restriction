"""
Channel Copier Bot - Main Entry Point
Auto-restore session, channels, bandwidth on restart.
Web server for Render health checks.
"""

import asyncio
import sys
import os

from aiohttp import web
from pyrogram import Client

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    OWNER_ID,
    PORT,
    BOT_SESSION_NAME,
    validate_config,
)

from utils.logger import logger
from auth.session_manager import session_mgr
from core.channel_manager import channel_mgr
from core.bandwidth import bandwidth

from handlers.commands import register_command_handlers
from handlers.messages import register_message_handlers
from handlers.callbacks import register_callback_handlers


# Use uvloop for better async performance on Linux
try:
    import uvloop

    uvloop.install()
    logger.info("uvloop enabled")

except ImportError:
    logger.info("uvloop not available, using default loop")


# ==================== WEB SERVER ====================

async def health_check(request):
    """Render health check endpoint."""

    return web.json_response({
        "status": "ok",
        "bot": "Channel Copier Bot",
        "logged_in": session_mgr.is_logged_in,
        "source": (
            channel_mgr.source_chat.title
            if channel_mgr.source_chat
            else None
        ),
        "destination": (
            channel_mgr.destination_chat.title
            if channel_mgr.destination_chat
            else None
        ),
    })


async def root_handler(request):
    """Root URL handler."""

    return web.Response(
        text=(
            "Channel Copier Bot is running!\n"
            "Made by @XyrDeveloper"
        ),
        content_type="text/plain",
    )


async def start_web_server():
    """Start aiohttp web server on PORT for Render."""

    app = web.Application()

    app.router.add_get("/", root_handler)
    app.router.add_get("/health", health_check)

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT,
    )

    await site.start()

    logger.info(
        f"Web server started on port {PORT}"
    )

    return runner


# ==================== AUTO RESTORE ====================

async def auto_restore(bot: Client):
    """
    Restore saved data after restart.

    1. Bandwidth counter
    2. Source channel settings
    3. User session
    4. Source/destination chat objects
    """

    logger.info(
        "Starting auto-restore..."
    )

    # Step 1: Load bandwidth
    bandwidth.load_from_file()

    logger.info(
        f"Bandwidth restored: "
        f"{bandwidth.bytes_used} bytes used"
    )

    # Step 2: Load channel settings
    channel_mgr.load_settings()

    # IMPORTANT:
    # Destination is now read ONLY from
    # DESTINATION_CHANNEL.
    #
    # Do NOT use channel_mgr._dest_id
    # because that attribute no longer exists.

    logger.info(
        f"Settings loaded - "
        f"Source ID: {channel_mgr._source_id}, "
        f"Dest ID: {channel_mgr.get_destination_id()}"
    )

    # Step 3: Auto-login userbot
    login_ok = await session_mgr.auto_login_from_file()

    if login_ok:

        logger.info(
            "Userbot auto-login successful"
        )

        # Step 4: Restore chat objects
        await channel_mgr.restore_chats(
            session_mgr.user_client
        )

        src_name = (
            channel_mgr.source_chat.title
            if channel_mgr.source_chat
            else "None"
        )

        dst_name = (
            channel_mgr.destination_chat.title
            if channel_mgr.destination_chat
            else "None"
        )

        logger.info(
            f"Channels restored - "
            f"Source: {src_name}, "
            f"Dest: {dst_name}"
        )

    else:

        logger.warning(
            "Userbot auto-login failed. "
            "Owner needs to /session or /login again."
        )

    return login_ok


# ==================== OWNER NOTIFICATION ====================

async def notify_owner(
    bot: Client,
    login_ok: bool,
):
    """Send startup status to owner's DM."""

    try:

        if login_ok:
            login_status = (
                "✅ Auto-login successful"
            )
        else:
            login_status = (
                "⚠️ Login needed — "
                "send /session or /login"
            )

        src = "❌ None"

        if channel_mgr.source_chat:
            src = (
                f"✅ {channel_mgr.source_chat.title}"
            )

        dst = "❌ None"

        if channel_mgr.destination_chat:
            dst = (
                f"✅ {channel_mgr.destination_chat.title}"
            )

        await bot.send_message(
            OWNER_ID,
            f"🚀 **Bot Restarted Successfully!**\n\n"
            f"🔐 Session: {login_status}\n"
            f"📥 Source: {src}\n"
            f"📤 Destination: {dst}\n\n"
            f"{bandwidth.format_status()}\n\n"
            f"💡 All settings restored from file.\n"
            f"— Extracted by @XyrDeveloper",
        )

        logger.info(
            "Owner notified"
        )

    except Exception as e:

        logger.warning(
            f"Could not notify owner: {e}"
        )
    # ==================== MAIN ENTRY POINT ====================

async def main():
    """Main function - starts everything."""

    logger.info("=" * 50)

    logger.info(
        "  Channel Copier Bot Starting..."
    )

    logger.info("=" * 50)

    # Validate environment variables
    try:

        validate_config()

        logger.info(
            "Configuration validated successfully"
        )

    except ValueError as e:

        logger.error(
            f"FATAL: {e}"
        )

        sys.exit(1)

    # Create bot client
    bot = Client(
        name=BOT_SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,
    )

    # Register command handlers
    register_command_handlers(bot)

    # Register message handlers
    register_message_handlers(bot)

    # Register callback handlers
    register_callback_handlers(bot)

    logger.info(
        "All handlers registered"
    )

    # Start web server
    web_runner = await start_web_server()

    # Start Telegram bot
    await bot.start()

    me = await bot.get_me()

    logger.info(
        f"Bot started as @{me.username} "
        f"(ID: {me.id})"
    )

    # Auto-restore everything
    login_ok = await auto_restore(bot)

    # Notify owner
    await notify_owner(
        bot,
        login_ok,
    )

    # Keep bot running
    logger.info(
        "Bot is now running and listening..."
    )

    try:

        stop_event = asyncio.Event()

        await stop_event.wait()

    except (
        KeyboardInterrupt,
        SystemExit,
    ):

        logger.info(
            "Shutdown signal received"
        )

    finally:

        logger.info(
            "Cleaning up..."
        )

        try:

            if session_mgr.user_client:

                await session_mgr.user_client.stop()

        except Exception:

            pass

        try:

            await bot.stop()

        except Exception:

            pass

        try:

            await web_runner.cleanup()

        except Exception:

            pass

        logger.info(
            "Bot stopped gracefully"
        )


# ==================== START ====================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        logger.info(
            "Interrupted by user"
        )

    except Exception as e:

        logger.error(
            f"Fatal error: {e}"
        )

        sys.exit(1)  
