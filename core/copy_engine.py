"""Copy engine - handles copy_message (native) with download+upload fallback"""
import os
import asyncio
from typing import Optional, List
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import (
    ChatForwardsRestricted,
    MessageIdInvalid,
    FloodWait,
)
from utils.logger import logger
from utils.caption import build_caption
from utils.progress import ProgressTracker
from core.bandwidth import bandwidth
from core.filters import matches_filter, get_file_size, detect_content_type, ContentType


class CopyEngine:
    """Handles copying messages using native copy first, then fallback to download+upload"""
    
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
        """Wait while paused, exit if stopped"""
        while self.is_paused and not self.is_stopped:
            await asyncio.sleep(1)
    
    async def copy_single_message(
        self,
        user_client: Client,
        bot_client: Client,
        source_chat_id: int,
        message_id: int,
        dest_chat_id: int,
    ) -> tuple[bool, str, int]:
        """
        Copy a single message from source to destination.
        Returns: (success, status_message, bytes_used)
        
        Strategy:
        1. Try user_client.copy_message() - zero bandwidth
        2. If restricted, check bandwidth quota
        3. If quota available: download + upload
        4. If quota exhausted: skip
        """
        try:
            # Get the source message
            src_msg = await user_client.get_messages(source_chat_id, message_id)
            
            if not src_msg or src_msg.empty:
                return False, "Message not found", 0
            
            # Build new caption
            original_caption = src_msg.caption or src_msg.text or ""
            new_caption = build_caption(original_caption if src_msg.caption else "")
            
            # STEP 1: Try native copy first (zero bandwidth)
            try:
                if src_msg.text and not src_msg.media:
                    # Pure text message
                    await user_client.send_message(
                        chat_id=dest_chat_id,
                        text=build_caption(src_msg.text),
                        disable_web_page_preview=True,
                    )
                else:
                    # Media or mixed
                    await user_client.copy_message(
                        chat_id=dest_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=message_id,
                        caption=new_caption if src_msg.media else None,
                    )
                return True, "Native copy successful", 0
            
            except ChatForwardsRestricted:
                logger.info(f"Message {message_id} restricted, trying download+upload")
                # Fall through to download+upload
            
            except FloodWait as e:
                logger.warning(f"FloodWait: sleeping {e.value}s")
                await asyncio.sleep(e.value)
                # Retry once
                try:
                    await user_client.copy_message(
                        chat_id=dest_chat_id,
                        from_chat_id=source_chat_id,
                        message_id=message_id,
                        caption=new_caption if src_msg.media else None,
                    )
                    return True, "Native copy successful (after wait)", 0
                except ChatForwardsRestricted:
                    pass
            
            # STEP 2: Check bandwidth quota before download
            if not bandwidth.can_download():
                return (
                    False,
                    "Bandwidth limit reached - skipped (copy-only mode)",
                    0,
                )
            
            # STEP 3: Download + Upload fallback
            return await self._download_upload_fallback(
                user_client, src_msg, dest_chat_id, new_caption
            )
        
        except MessageIdInvalid:
            return False, "Invalid message ID", 0
        except Exception as e:
            logger.error(f"Copy failed for message {message_id}: {e}")
            return False, f"Error: {str(e)[:80]}", 0
    
    async def _download_upload_fallback(
        self,
        user_client: Client,
        src_msg: Message,
        dest_chat_id: int,
        caption: str,
    ) -> tuple[bool, str, int]:
        """Download from source, then re-upload to destination"""
        file_path = None
        try:
            file_size = get_file_size(src_msg)
            
            # Double check bandwidth
            if not bandwidth.can_download():
                return False, "Bandwidth limit reached", 0
            
            # Download
            file_path = await user_client.download_media(
                src_msg,
                file_name=os.path.join(self.download_dir, ""),
            )
            
            if not file_path:
                return False, "Download failed", 0
            
            # Actual file size
            actual_size = os.path.getsize(file_path)
            bytes_used = actual_size * 2  # Download + Upload
            
            # Upload based on content type
            ctype = detect_content_type(src_msg)
            
            if ctype == ContentType.VIDEO:
                await user_client.send_video(
                    chat_id=dest_chat_id,
                    video=file_path,
                    caption=caption,
                    thumb=None,  # No thumbnail
                )
            elif ctype in (ContentType.PDF, ContentType.DOCUMENT):
                await user_client.send_document(
                    chat_id=dest_chat_id,
                    document=file_path,
                    caption=caption,
                    thumb=None,
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
                    thumb=None,
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
            return True, "Downloaded and uploaded", bytes_used
        
        except FloodWait as e:
            logger.warning(f"FloodWait during upload: {e.value}s")
            await asyncio.sleep(e.value)
            return False, f"FloodWait: {e.value}s", 0
        
        except Exception as e:
            logger.error(f"Download/upload failed: {e}")
            return False, f"Upload error: {str(e)[:80]}", 0
        
        finally:
            # Cleanup downloaded file
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
    
    async def copy_range(
        self,
        user_client: Client,
        bot_client: Client,
        source_chat_id: int,
        dest_chat_id: int,
        start_id: int,
        end_id: int,
        filter_type: str = "all",
        status_message: Optional[Message] = None,
    ) -> ProgressTracker:
        """
        Copy a range of messages with optional filtering.
        Updates status_message periodically.
        """
        self.is_running = True
        self.reset_flags()
        
        # Build message ID list
        message_ids = list(range(start_id, end_id + 1))
        
        # Filter messages if needed
        if filter_type != "all":
            filtered_ids = []
            try:
                # Get all messages in range
                msgs = await user_client.get_messages(source_chat_id, message_ids)
                if not isinstance(msgs, list):
                    msgs = [msgs]
                for msg in msgs:
                    if msg and not msg.empty and matches_filter(msg, filter_type):
                        filtered_ids.append(msg.id)
            except Exception as e:
                logger.error(f"Filter fetch error: {e}")
                filtered_ids = message_ids
            message_ids = filtered_ids
        
        progress = ProgressTracker(total=len(message_ids))
        self.current_progress = progress
        
        last_update_time = 0
        update_interval = 5  # Update status every 5 seconds
        
        for msg_id in message_ids:
            # Check control flags
            if self.is_stopped:
                break
            
            await self._wait_if_paused()
            
            if self.skip_current:
                self.skip_current = False
                progress.increment_skipped()
                continue
            
            progress.current_file = f"Message {msg_id}"
            
            success, status_msg, bytes_used = await self.copy_single_message(
                user_client, bot_client, source_chat_id, msg_id, dest_chat_id
            )
            
            if success:
                progress.increment_success(bytes_used)
            else:
                if "skipped" in status_msg.lower() or "bandwidth" in status_msg.lower():
                    progress.increment_skipped()
                else:
                    progress.increment_failed()
            
            # Update status message periodically
            import time
            now = time.time()
            if status_message and (now - last_update_time) > update_interval:
                try:
                    await status_message.edit_text(
                        f"⏳ **Copying in progress...**\n\n"
                        f"{progress.format_summary()}\n\n"
                        f"📄 Current: `{progress.current_file}`\n\n"
                        f"Controls: /pause /resume /stop /skip"
                    )
                    last_update_time = now
                except Exception:
                    pass
            
            # Small delay to prevent flooding
            await asyncio.sleep(0.5)
        
        self.is_running = False
        return progress
    
    async def copy_all(
        self,
        user_client: Client,
        bot_client: Client,
        source_chat_id: int,
        dest_chat_id: int,
        filter_type: str = "all",
        status_message: Optional[Message] = None,
        limit: int = 0,
    ) -> ProgressTracker:
        """Copy all messages from a channel"""
        self.is_running = True
        self.reset_flags()
        
        # Collect message IDs first
        message_ids = []
        try:
            async for msg in user_client.get_chat_history(source_chat_id, limit=limit or 0):
                if filter_type == "all" or matches_filter(msg, filter_type):
                    message_ids.append(msg.id)
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
        
        # Reverse to copy oldest first
        message_ids.reverse()
        
        progress = ProgressTracker(total=len(message_ids))
        self.current_progress = progress
        
        last_update_time = 0
        
        for msg_id in message_ids:
            if self.is_stopped:
                break
            await self._wait_if_paused()
            
            if self.skip_current:
                self.skip_current = False
                progress.increment_skipped()
                continue
            
            progress.current_file = f"Message {msg_id}"
            
            success, _, bytes_used = await self.copy_single_message(
                user_client, bot_client, source_chat_id, msg_id, dest_chat_id
            )
            
            if success:
                progress.increment_success(bytes_used)
            else:
                progress.increment_failed()
            
            import time
            now = time.time()
            if status_message and (now - last_update_time) > 5:
                try:
                    await status_message.edit_text(
                        f"⏳ **Copying in progress...**\n\n"
                        f"{progress.format_summary()}\n\n"
                        f"Controls: /pause /resume /stop /skip"
                    )
                    last_update_time = now
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


# Global instance
copy_engine = CopyEngine()
