"""
Channel Copier Bot - Main Entry Point
Handles bot startup, web server for Render, and graceful shutdown.
"""
import asyncio
import os
import sys
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
from handlers.commands import register_command_handlers
from handlers.messages import register_message_handlers
from handlers.callbacks import register_callback_handlers

# Use uvloop for better performance on Linux
try:
    import uvloop
    uvloop.install()
    logger.info("Using uvloop for asyncio")
except ImportError:
    logger.info("uvloop not available, using default event loop")


# ==================== WEB SERVER (for Render) ====================

async def health_check(request):
    """Health check endpoint for Render"""
    return web.json_response({
        "status": "ok",
        "bot": "Channel Copier Bot",
        "version": "1.0.0",
    })


async def root_handler(request):
    """Root endpoint"""
    return web.Response(
        text="Channel Copier Bot is running!\nMade by @XyrDeveloper",
        content_type="text/plain",
    )


async def start_web_server():
    """Start the aiohttp web server for Render health checks"""
    app = web.Application()
    app.router.add_get("/", root_handler)
    app.router.add_get("/health", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")
    return runner


# ==================== BOT STARTUP ====================

async def startup_notify(bot: Client):
    """Send a startup notification to the owner"""
    try:
        await bot.send_message(
            OWNER_ID,
            "🚀 **Bot Started!**\n\n"
            "✅ Server is running\n"
            "⚠️ Please login using /login or /session\n\n"
            "Use /help to see available commands.",
        )
    except Exception as e:
        logger.warning(f"Could not notify owner: {e}")


async def main():
    """Main entry point"""
    logger.info("=" * 50)
    logger.info("Channel Copier Bot Starting...")
    logger.info("=" * 50)
    
    # Validate config
    try:
        validate_config()
        logger.info("Configuration validated")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Create bot client
    bot = Client(
        name=BOT_SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,
    )
    
    # Register all handlers
    register_command_handlers(bot)
    register_message_handlers(bot)
    register_callback_handlers(bot)
    
    # Start web server (for Render)
    web_runner = await start_web_server()
    
    # Start bot
    await bot.start()
    me = await bot.get_me()
    logger.info(f"Bot started as @{me.username} (ID: {me.id})")
    
    # Notify owner
    await startup_notify(bot)
    
    # Keep running
    try:
        # Idle - keeps the event loop alive
        stop_event = asyncio.Event()
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        await bot.stop()
        await web_runner.cleanup()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
