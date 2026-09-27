"""Copy engine - Handles native copy and download+upload fallback"""
import os
import asyncio
import time
from typing import Optional
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import ChatForwardsRestricted, MessageIdInvalid, FloodWait
from utils.logger import logger
from utils.caption import build_caption
from utils.progress import ProgressTracker
from core.bandwidth import bandwidth
from core.filters import matches_filter, detect_content_type, ContentType


class CopyEngine:
    def __init__(self):
        self.current_progress: Optional[ProgressTracker] = None
        self.is_running: bool = False
        self.is_paused: bool = False
        self.is_stopped: bool = False
        self.skip_current: bool = False
        self.download_dir: str = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)

    def reset_flags(self):
        self.is_paused = False
        self.is_stopped = False
        self.skip_current = False

    async def _wait_if_paused(self):
        while self.is_paused and not self.is_stopped:
            await asyncio.sleep(1)

    async def copy_single_message(
        self,
        user_client: Client,
        source_chat_id: int,
        message_id: int,
        dest_chat_id: int,
        bot_client: Optional[Client] = None,
        **kwargs
    ) -> tuple:
        """
        Copy single message to target destination.
        Returns: (success: bool, status_text: str, bytes_used: int)
        """
        try:
            src_msg = await user_client.get_messages(source_chat_id, message_id)
            if not src_msg or src_msg.empty:
                return False, "Empty message", 0

            original_caption = src_msg.caption or ""
            new_caption = build_caption(original_caption)

            # STEP 1: Native Copy (Zero Bandwidth)
            try:
                if src_msg.text and not src_msg.media:
                    await user_client.send_message(
                        chat_id=dest_chat_id,
                        text=build_caption(src_msg.text),
                    )
                else:
                    await user_client.copy_message(
                        chat_id=dest_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=message_id,
                        caption=new_caption if src_msg.media else None,
                    )
                return True, "Native copy successful", 0

            except ChatForwardsRestricted:
                logger.info(f"Message {message_id} restricted, using download fallback")

            except FloodWait as e:
                await asyncio.sleep(e.value)
                try:
                    await user_client.copy_message(
                        chat_id=dest_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=message_id,
                        caption=new_caption if src_msg.media else None,
                    )
                    return True, "Native copy (retry)", 0
                except ChatForwardsRestricted:
                    pass

            # STEP 2: Bandwidth Check
            if not bandwidth.can_download():
                return False, "Bandwidth limit reached - skipped", 0

            # STEP 3: Fallback Download + Upload
            return await self._download_upload(
                user_client, src_msg, dest_chat_id, new_caption
            )

        except MessageIdInvalid:
            return False, "Invalid message ID", 0
        except Exception as e:
            logger.error(f"Copy failed for msg {message_id}: {e}")
            return False, f"Error: {str(e)[:80]}", 0

    async def _download_upload(
        self,
        user_client: Client,
        src_msg: Message,
        dest_chat_id: int,
        caption: str,
    ) -> tuple:
        """Download to disk and re-upload to target destination"""
        file_path = None
        try:
            if not bandwidth.can_download():
                return False, "Bandwidth limit", 0

            file_path = await user_client.download_media(
                src_msg,
                file_name=os.path.join(self.download_dir, ""),
            )
            if not file_path:
                return False, "Download failed", 0

            actual_size = os.path.getsize(file_path)
            bytes_used = actual_size * 2

            ctype = detect_content_type(src_msg)

            if ctype == ContentType.VIDEO:
                await user_client.send_video(
                    chat_id=dest_chat_id,
                    video=file_path,
                    caption=caption,
                )
            elif ctype in (ContentType.PDF, ContentType.DOCUMENT):
                await user_client.send_document(
                    chat_id=dest_chat_id,
                    document=file_path,
                    caption=caption,
                )
            elif ctype == ContentType.PHOTO:
                await user_client.send_photo(
                    chat_id=dest_chat_id,
                    photo=file_path,
                    caption=caption,
                )
            elif ctype == ContentType.AUDIO:
                await user_client.send_audio(
                    chat_id=dest_chat_id,
                    audio=file_path,
                    caption=caption,
                )
            elif ctype == ContentType.ANIMATION:
                await user_client.send_animation(
                    chat_id=dest_chat_id,
                    animation=file_path,
                    caption=caption,
                )
            elif ctype == ContentType.VOICE:
                await user_client.send_voice(
                    chat_id=dest_chat_id,
                    voice=file_path,
                    caption=caption,
                )
            else:
                await user_client.send_document(
                    chat_id=dest_chat_id,
                    document=file_path,
                    caption=caption,
                )

            bandwidth.add_usage(bytes_used)
            bandwidth.save_to_file()
            return True, "Download+Upload", bytes_used

        except FloodWait as e:
            await asyncio.sleep(e.value)
            return False, f"FloodWait {e.value}s", 0
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False, f"Upload error: {str(e)[:80]}", 0
        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

    async def copy_range(
        self,
        user_client: Client,
        source_chat_id: int,
        dest_chat_id: int,
        start_id: int,
        end_id: int,
        filter_type: str = "all",
        status_message: Optional[Message] = None,
        bot_client: Optional[Client] = None,
        **kwargs
    ) -> ProgressTracker:
        """Copy a range of messages from source to dest"""
        self.is_running = True
        self.reset_flags()

        message_ids = list(range(start_id, end_id + 1))

        if filter_type != "all":
            filtered = []
            try:
                msgs = await user_client.get_messages(source_chat_id, message_ids)
                if not isinstance(msgs, list):
                    msgs = [msgs]
                for msg in msgs:
                    if msg and not msg.empty and matches_filter(msg, filter_type):
                        filtered.append(msg.id)
            except Exception:
                filtered = message_ids
            message_ids = filtered

        progress = ProgressTracker(total=len(message_ids))
        self.current_progress = progress
        last_update = 0

        for msg_id in message_ids:
            if self.is_stopped:
                break
            await self._wait_if_paused()
            if self.skip_current:
                self.skip_current = False
                progress.increment_skipped()
                continue

            progress.current_file = f"Msg {msg_id}"
            success, status_msg, bytes_used = await self.copy_single_message(
                user_client=user_client,
                source_chat_id=source_chat_id,
                message_id=msg_id,
                dest_chat_id=dest_chat_id,
                bot_client=bot_client,
            )
            if success:
                progress.increment_success(bytes_used)
            elif "skipped" in status_msg.lower() or "bandwidth" in status_msg.lower():
                progress.increment_skipped()
            else:
                progress.increment_failed()

            now = time.time()
            if status_message and (now - last_update) > 5:
                try:
                    await status_message.edit_text(
                        f"⏳ **Copying in progress...**\n\n{progress.format_summary()}\n\n"
                        f"Controls: /pause /resume /stop /skip"
                    )
                    last_update = now
                except Exception:
                    pass

            await asyncio.sleep(0.5)

        self.is_running = False
        return progress

    async def copy_all(
        self,
        user_client: Client,
        source_chat_id: int,
        dest_chat_id: int,
        filter_type: str = "all",
        status_message: Optional[Message] = None,
        limit: int = 0,
        bot_client: Optional[Client] = None,
        **kwargs
    ) -> ProgressTracker:
        """Copy all messages from source channel"""
        self.is_running = True
        self.reset_flags()

        message_ids = []
        try:
            async for msg in user_client.get_chat_history(source_chat_id, limit=limit or 0):
                if filter_type == "all" or matches_filter(msg, filter_type):
                    message_ids.append(msg.id)
        except Exception as e:
            logger.error(f"Fetch error: {e}")

        message_ids.reverse()
        progress = ProgressTracker(total=len(message_ids))
        self.current_progress = progress
        last_update = 0

        for msg_id in message_ids:
            if self.is_stopped:
                break
            await self._wait_if_paused()
            if self.skip_current:
                self.skip_current = False
                progress.increment_skipped()
                continue

            success, status_msg, bytes_used = await self.copy_single_message(
                user_client=user_client,
                source_chat_id=source_chat_id,
                message_id=msg_id,
                dest_chat_id=dest_chat_id,
                bot_client=bot_client,
            )
            if success:
                progress.increment_success(bytes_used)
            elif "skipped" in status_msg.lower() or "bandwidth" in status_msg.lower():
                progress.increment_skipped()
            else:
                progress.increment_failed()

            now = time.time()
            if status_message and (now - last_update) > 5:
                try:
                    await status_message.edit_text(
                        f"⏳ **Copying in progress...**\n\n{progress.format_summary()}\n\n"
                        f"Controls: /pause /resume /stop /skip"
                    )
                    last_update = now
                except Exception:
                    pass
            await asyncio.sleep(0.5)

        self.is_running = False
        return progress

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        self.is_stopped = True
        self.is_paused = False

    def skip(self):
        self.skip_current = True


copy_engine = CopyEngine()
