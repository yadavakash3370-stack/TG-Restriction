"""Channel manager with Environment Variable fallback & Strict Channel Resolution"""
import json
import os
from typing import Optional, List, Dict, Union
from pyrogram import Client
from pyrogram.types import Chat
from config import SETTINGS_FILE, DESTINATION_CHANNEL, SOURCE_CHANNEL
from utils.logger import logger
from core.filters import detect_content_type, ContentType


class ChannelManager:
    def __init__(self):
        self.source_chat: Optional[Chat] = None
        self.destination_chat: Optional[Chat] = None
        self.last_analysis: Optional[Dict] = None
        self.pending_search_results: List[Chat] = []
        self.pending_search_type: Optional[str] = None

        self._source_id: Optional[Union[int, str]] = None
        self._dest_id: Optional[Union[int, str]] = None

    def save_settings(self):
        data = {
            "source_id": self._source_id,
            "dest_id": self._dest_id,
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Save settings failed: {e}")

    def load_settings(self):
        # 1. Priority: Render Environment Variables
        if DESTINATION_CHANNEL:
            self._dest_id = int(DESTINATION_CHANNEL) if (DESTINATION_CHANNEL.startswith("-") or DESTINATION_CHANNEL.isdigit()) else DESTINATION_CHANNEL
        if SOURCE_CHANNEL:
            self._source_id = int(SOURCE_CHANNEL) if (SOURCE_CHANNEL.startswith("-") or SOURCE_CHANNEL.isdigit()) else SOURCE_CHANNEL

        # 2. Priority: Local settings file
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                if not self._source_id:
                    self._source_id = data.get("source_id")
                if not self._dest_id:
                    self._dest_id = data.get("dest_id")
                return True
        except Exception as e:
            logger.error(f"Load settings failed: {e}")
        return False

    async def restore_chats(self, client: Client):
        self.load_settings()

        if self._source_id:
            try:
                self.source_chat = await client.get_chat(self._source_id)
                logger.info(f"Source restored: {self.source_chat.title}")
            except Exception as e:
                logger.warning(f"Source restore failed: {e}")

        if self._dest_id:
            try:
                self.destination_chat = await client.get_chat(self._dest_id)
                logger.info(f"Destination restored: {self.destination_chat.title} ({self.destination_chat.id})")
            except Exception as e:
                logger.warning(f"Destination restore failed ({self._dest_id}): {e}")

    def set_source(self, chat: Chat):
        self.source_chat = chat
        self._source_id = chat.id
        self.last_analysis = None
        self.save_settings()

    def set_destination(self, chat: Chat):
        self.destination_chat = chat
        self._dest_id = chat.id
        self.save_settings()

    def clear_source(self):
        self.source_chat = None
        self._source_id = None
        self.last_analysis = None
        self.save_settings()

    def clear_destination(self):
        self.destination_chat = None
        self._dest_id = None
        self.save_settings()

    def get_destination_id(self) -> Optional[Union[int, str]]:
        if self.destination_chat:
            return self.destination_chat.id
        return self._dest_id

    async def search_channels(self, client: Client, query: str) -> List[Chat]:
        results: List[Chat] = []
        seen_ids = set()
        query_clean = query.strip().lstrip("@").lower()

        if query.startswith("@") or "t.me/" in query:
            username = query.replace("https://t.me/", "").replace("t.me/", "").lstrip("@")
            try:
                chat = await client.get_chat(username)
                if chat.id not in seen_ids:
                    results.append(chat)
                    seen_ids.add(chat.id)
                return results
            except Exception:
                pass

        try:
            async for dialog in client.get_dialogs():
                chat = dialog.chat
                if chat.type.name in ("CHANNEL", "SUPERGROUP", "GROUP"):
                    title = (chat.title or "").lower()
                    username = (chat.username or "").lower()
                    if query_clean in title or query_clean in username:
                        if chat.id not in seen_ids:
                            results.append(chat)
                            seen_ids.add(chat.id)
        except Exception as e:
            logger.error(f"Dialog search error: {e}")

        try:
            async for chat in client.search_global(query, limit=10):
                if hasattr(chat, "chat") and chat.chat:
                    c = chat.chat
                    if c.type.name in ("CHANNEL", "SUPERGROUP", "GROUP"):
                        if c.id not in seen_ids:
                            results.append(c)
                            seen_ids.add(c.id)
        except Exception:
            pass

        return results[:10]

    async def analyze_channel(self, client: Client, limit: int = 500) -> Dict:
        if not self.source_chat:
            return {}
        counts = {
            "video": 0, "pdf": 0, "document": 0, "photo": 0,
            "audio": 0, "voice": 0, "sticker": 0, "animation": 0,
            "text": 0, "other": 0, "total": 0, "total_files": 0,
        }
        try:
            async for msg in client.get_chat_history(self.source_chat.id, limit=limit):
                counts["total"] += 1
                ctype = detect_content_type(msg)
                if ctype == ContentType.VIDEO:
                    counts["video"] += 1
                    counts["total_files"] += 1
                elif ctype == ContentType.PDF:
                    counts["pdf"] += 1
                    counts["total_files"] += 1
                elif ctype == ContentType.DOCUMENT:
                    counts["document"] += 1
                    counts["total_files"] += 1
                elif ctype == ContentType.PHOTO:
                    counts["photo"] += 1
                    counts["total_files"] += 1
                elif ctype == ContentType.AUDIO:
                    counts["audio"] += 1
                    counts["total_files"] += 1
                elif ctype == ContentType.VOICE:
                    counts["voice"] += 1
                elif ctype == ContentType.ANIMATION:
                    counts["animation"] += 1
                    counts["total_files"] += 1
                elif ctype == ContentType.TEXT:
                    counts["text"] += 1
                else:
                    counts["other"] += 1
        except Exception as e:
            logger.error(f"Analysis error: {e}")
        self.last_analysis = counts
        return counts

    def format_analysis(self, analysis: Dict) -> str:
        return (
            f"📊 **Channel Analysis**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎬 Videos: `{analysis.get('video', 0)}`\n"
            f"📄 PDFs: `{analysis.get('pdf', 0)}`\n"
            f"📁 Documents: `{analysis.get('document', 0)}`\n"
            f"🖼 Photos: `{analysis.get('photo', 0)}`\n"
            f"🎵 Audio: `{analysis.get('audio', 0)}`\n"
            f"📝 Text: `{analysis.get('text', 0)}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Total: `{analysis.get('total', 0)}`\n"
            f"📁 Files: `{analysis.get('total_files', 0)}`"
        )

    def get_status(self) -> str:
        src = "❌ Not connected"
        if self.source_chat:
            src = f"✅ {self.source_chat.title} (`{self.source_chat.id}`)"
        dst = "❌ Not set"
        if self.destination_chat:
            dst = f"✅ {self.destination_chat.title} (`{self.destination_chat.id}`)"
        elif self._dest_id:
            dst = f"⚠️ Target ID: `{self._dest_id}`"
        return (
            f"🔗 **Channels**\n"
            f"📥 Source: {src}\n"
            f"📤 Destination: {dst}"
        )


channel_mgr = ChannelManager()
