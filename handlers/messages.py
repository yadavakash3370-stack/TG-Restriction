"""Message handlers."""

import re
import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

from auth.permissions import permissions
from auth.session_manager import session_mgr
from core.channel_manager import channel_mgr
from core.copy_engine import copy_engine
from utils.logger import logger


TG_LINK_PATTERN = re.compile(
    r"https?://t\.me/(?:c/)?([\w\d_]+)/(\d+)(?:-(\d+))?"
)


async def handle_login_input(
    client: Client,
    message: Message
):

    if message.chat.type.name != "PRIVATE":
        return

    user_id = permissions.get_user_id(message)

    if not permissions.is_admin_or_higher(user_id):
        return

    text = message.text.strip()

    if text.startswith("/"):
        return

    state = session_mgr.login_state

    if state == "awaiting_phone":

        if not text.startswith("+"):
            await message.reply_text(
                "Format: `+919876543210`"
            )
            return

        status = await message.reply_text(
            "Sending OTP..."
        )

        ok, msg = await session_mgr.start_phone_login(
            text
        )

        await status.edit_text(
            f"{'Success' if ok else 'Failed'}: {msg}"
        )

    elif state == "awaiting_code":

        code = (
            text
            .replace(" ", "")
            .replace("-", "")
        )

        status = await message.reply_text(
            "Verifying..."
        )

        ok, msg = await session_mgr.verify_code(
            code
        )

        await status.edit_text(
            f"{'Success' if ok else 'Failed'}: {msg}"
        )

    elif state == "awaiting_password":

        try:
            await message.delete()
        except Exception:
            pass

        status = await client.send_message(
            message.chat.id,
            "Checking 2FA..."
        )

        ok, msg = await session_mgr.verify_password(
            text
        )

        await status.edit_text(
            f"{'Success' if ok else 'Failed'}: {msg}"
        )


async def handle_telegram_link(
    client: Client,
    message: Message
):
    """
    Handles Telegram links.

    IMPORTANT:
    Destination is ALWAYS DESTINATION_CHANNEL.
    The chat where the link was sent is NEVER used
    as the destination.
    """

    text = message.text or message.caption or ""

    matches = TG_LINK_PATTERN.findall(text)

    if not matches:
        return

    user_id = permissions.get_user_id(message)

    if not permissions.is_authorized(user_id):
        return

    # ---------------------------------------------------------
    # DELETE LINK MESSAGE
    # ---------------------------------------------------------

    try:
        await message.delete()
    except Exception:
        pass

    # ---------------------------------------------------------
    # FIXED DESTINATION
    # ---------------------------------------------------------

    dest_chat_id = channel_mgr.get_destination_id()

    if not dest_chat_id:
        try:
            temp = await client.send_message(
                message.chat.id,
                "Destination channel is not configured.\n\n"
                "Set DESTINATION_CHANNEL in Render Environment Variables."
            )

            await asyncio.sleep(8)

            try:
                await temp.delete()
            except Exception:
                pass

        except Exception:
            pass

        return

    # ---------------------------------------------------------
    # NEVER ALLOW A USER CHAT AS DESTINATION
    # ---------------------------------------------------------

    if (
        isinstance(dest_chat_id, int)
        and dest_chat_id > 0
    ):
        logger.error(
            f"Invalid DESTINATION_CHANNEL: {dest_chat_id}"
        )

        try:
            temp = await client.send_message(
                message.chat.id,
                "Invalid destination channel configuration.\n\n"
                "Use a Telegram channel ID such as -1001234567890 "
                "or a channel username."
            )

            await asyncio.sleep(8)

            try:
                await temp.delete()
            except Exception:
                pass

        except Exception:
            pass

        return

    # ---------------------------------------------------------
    # USER SESSION CHECK
    # ---------------------------------------------------------

    if not session_mgr.is_logged_in:

        try:
            temp = await client.send_message(
                message.chat.id,
                "User session is not logged in."
            )

            await asyncio.sleep(6)

            try:
                await temp.delete()
            except Exception:
                pass

        except Exception:
            pass

        return

    # ---------------------------------------------------------
    # PROCESS LINKS
    # ---------------------------------------------------------

    for chat_ref, start_str, end_str in matches:

        try:

            start_id = int(start_str)

            end_id = (
                int(end_str)
                if end_str
                else start_id
            )

            # -------------------------------------------------
            # SOURCE RESOLUTION
            # -------------------------------------------------

            if chat_ref.isdigit():

                source_id = int(
                    f"-100{chat_ref}"
                )

            else:

                try:

                    source_chat = (
                        await session_mgr.user_client.get_chat(
                            chat_ref
                        )
                    )

                    source_id = source_chat.id

                except Exception as e:

                    logger.error(
                        f"Source resolution failed: {e}"
                    )

                    continue

            # -------------------------------------------------
            # STATUS MESSAGE
            # -------------------------------------------------

            try:

                status_msg = await client.send_message(
                    message.chat.id,
                    f"Processing {start_id}"
                    + (
                        f" to {end_id}"
                        if end_id != start_id
                        else ""
                    )
                    + "..."
                )

            except Exception:

                status_msg = None

            copied = 0

            # -------------------------------------------------
            # PROCESS RANGE
            # -------------------------------------------------

            for msg_id in range(
                start_id,
                end_id + 1
            ):

                success, status_text, _ = (
                    await copy_engine.copy_single_message(
                        user_client=session_mgr.user_client,
                        source_chat_id=source_id,
                        message_id=msg_id,
                        dest_chat_id=dest_chat_id,
                    )
                )

                if success:
                    copied += 1

                await asyncio.sleep(0.5)

            # -------------------------------------------------
            # COMPLETE
            # -------------------------------------------------

            if status_msg:

                try:

                    await status_msg.edit_text(
                        f"Completed. {copied} item(s) processed."
                    )

                    await asyncio.sleep(5)

                    await status_msg.delete()

                except Exception:
                    pass

        except Exception as e:

            logger.error(
                f"Link processing error: {e}"
            )


def register_message_handlers(
    app: Client
):

    # ---------------------------------------------------------
    # TELEGRAM LINK HANDLER
    # ---------------------------------------------------------

    app.add_handler(
        MessageHandler(
            handle_telegram_link,
            filters.text
            & filters.regex(
                TG_LINK_PATTERN.pattern
            )
        ),
        group=1
    )

    # ---------------------------------------------------------
    # LOGIN INPUT HANDLER
    # ---------------------------------------------------------

    app.add_handler(
        MessageHandler(
            handle_login_input,
            filters.text
            & filters.private
            & ~filters.command([
                "start",
                "help",
                "status",
                "login",
                "session",
                "logout",
                "connect",
                "disconnect",
                "analyze",
                "copy",
                "v",
                "p",
                "d",
                "a",
                "pause",
                "resume",
                "stop",
                "skip",
                "mode",
                "limit",
                "reset",
                "progress",
                "speed",
                "adduser",
                "addadmin",
                "removeuser",
                "removeadmin",
                "userlist",
                "broadcast",
                "cancel",
            ])
        ),
        group=2
    )

    logger.info(
        "Message handlers registered"
                )
