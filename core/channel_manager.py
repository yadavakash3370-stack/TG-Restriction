"""Channel manager - fixed destination from DESTINATION_CHANNEL only."""

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

    # ---------------------------------------------------------
    # ID HELPERS
    # ---------------------------------------------------------

    @staticmethod
    def normalize_chat_id(value):
        """Convert numeric channel IDs to int, usernames remain strings."""
        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        try:
            return int(value)
        except ValueError:
            return value

    # ---------------------------------------------------------
    # SETTINGS
    # ---------------------------------------------------------

    def save_settings(self):
        """
        Save ONLY source settings.

        Destination is intentionally NOT saved here.
        Destination always comes from DESTINATION_CHANNEL.
        """
        data = {
            "source_id": self._source_id
        }

        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Save settings failed: {e}")

    def load_settings(self):
        """
        Load source from environment/settings.

        Destination is NEVER loaded from settings.json.
        """

        if SOURCE_CHANNEL:
            self._source_id = self.normalize_chat_id(SOURCE_CHANNEL)

        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)

                if not self._source_id:
                    self._source_id = data.get("source_id")

                return True

        except Exception as e:
            logger.error(f"Load settings failed: {e}")

        return False

    # ---------------------------------------------------------
    # CHAT RESTORE
    # ---------------------------------------------------------

    async def restore_chats(self, client: Client):
        self.load_settings()

        # Restore source only
        if self._source_id:
            try:
                self.source_chat = await client.get_chat(self._source_id)

                logger.info(
                    f"Source restored: "
                    f"{self.source_chat.title} "
                    f"({self.source_chat.id})"
                )

            except Exception as e:
                logger.warning(f"Source restore failed: {e}")

        # Destination is loaded ONLY from ENV
        destination_id = self.get_destination_id()

        if destination_id:
            try:
                self.destination_chat = await client.get_chat(
                    destination_id
                )

                logger.info(
                    f"Destination loaded from ENV: "
                    f"{self.destination_chat.title} "
                    f"({self.destination_chat.id})"
                )

            except Exception as e:
                logger.error(
                    f"Destination channel could not be resolved "
                    f"from DESTINATION_CHANNEL={destination_id}: {e}"
                )
                self.destination_chat = None

    # ---------------------------------------------------------
    # SOURCE
    # ---------------------------------------------------------

    def set_source(self, chat: Chat):
        self.source_chat = chat
        self._source_id = chat.id
        self.last_analysis = None
        self.save_settings()

    def clear_source(self):
        self.source_chat = None
        self._source_id = None
        self.last_analysis = None
        self.save_settings()

    # ---------------------------------------------------------
    # DESTINATION
    # ---------------------------------------------------------

    def get_destination_id(self):
        """
        IMPORTANT:
        Destination ALWAYS comes from DESTINATION_CHANNEL.

        No /setdest.
        No settings.json destination.
        No current-chat fallback.
        No Saved Messages fallback.
        """

        if not DESTINATION_CHANNEL:
            return None

        return self.normalize_chat_id(DESTINATION_CHANNEL)

    def get_destination_chat(self):
        return self.destination_chat

    # ---------------------------------------------------------
    # CHANNEL SEARCH
    # ---------------------------------------------------------

    async def search_channels(
        self,
        client: Client,
        query: str
    ) -> List[Chat]:

        results: List[Chat] = []
        seen_ids = set()

        query_clean = query.strip().lstrip("@").lower()

        # Direct username / t.me link
        if query.startswith("@") or "t.me/" in query:
            username = (
                query
                .replace("https://t.me/", "")
                .replace("http://t.me/", "")
                .replace("t.me/", "")
                .lstrip("@")
                .split("/")[0]
            )

            try:
                chat = await client.get_chat(username)

                if chat.id not in seen_ids:
                    results.append(chat)
                    seen_ids.add(chat.id)

                return results

            except Exception:
                pass

        # Joined dialogs
        try:
            async for dialog in client.get_dialogs():

                chat = dialog.chat

                if chat.type.name in (
                    "CHANNEL",
                    "SUPERGROUP",
                    "GROUP"
                ):

                    title = (chat.title or "").lower()
                    username = (chat.username or "").lower()

                    if (
                        query_clean in title
                        or query_clean in username
                    ):

                        if chat.id not in seen_ids:
                            results.append(chat)
                            seen_ids.add(chat.id)

        except Exception as e:
            logger.error(f"Dialog search error: {e}")

        # Global search
        try:
            async for chat in client.search_global(
                query,
                limit=10
            ):

                if hasattr(chat, "chat") and chat.chat:

                    c = chat.chat

                    if c.type.name in (
                        "CHANNEL",
                        "SUPERGROUP",
                        "GROUP"
                    ):

                        if c.id not in seen_ids:
                            results.append(c)
                            seen_ids.add(c.id)

        except Exception:
            pass

        return results[:10]

    # ---------------------------------------------------------
    # ANALYSIS
    # ---------------------------------------------------------

    async def analyze_channel(
        self,
        client: Client,
        limit: int = 500
    ) -> Dict:

        if not self.source_chat:
            return {}

        counts = {
            "video": 0,
            "pdf": 0,
            "document": 0,
            "photo": 0,
            "audio": 0,
            "voice": 0,
            "sticker": 0,
            "animation": 0,
            "text": 0,
            "other": 0,
            "total": 0,
            "total_files": 0,
        }

        try:

            async for msg in client.get_chat_history(
                self.source_chat.id,
                limit=limit
            ):

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

    # ---------------------------------------------------------
    # FORMAT ANALYSIS
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    def get_status(self) -> str:

        if self.source_chat:
            src = (
                f"✅ {self.source_chat.title} "
                f"(`{self.source_chat.id}`)"
            )
        else:
            src = "❌ Not connected"

        destination_id = self.get_destination_id()

        if self.destination_chat:
            dst = (
                f"✅ {self.destination_chat.title} "
                f"(`{self.destination_chat.id}`)"
            )

        elif destination_id:
            dst = f"⚠️ Configured: `{destination_id}`"

        else:
            dst = "❌ DESTINATION_CHANNEL is not configured"

        return (
            f"🔗 **Channels**\n"
            f"📥 Source: {src}\n"
            f"📤 Destination: {dst}"
        )


channel_mgr = ChannelManager()
