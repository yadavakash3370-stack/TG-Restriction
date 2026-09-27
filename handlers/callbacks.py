"""Callback query handlers (for inline buttons)"""
from pyrogram import Client
from pyrogram.types import CallbackQuery
from pyrogram.handlers import CallbackQueryHandler
from utils.logger import logger


async def handle_callback(client: Client, query: CallbackQuery):
    """Generic callback handler"""
    await query.answer()


def register_callback_handlers(app: Client):
    """Register callback handlers"""
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("Callback handlers registered")
