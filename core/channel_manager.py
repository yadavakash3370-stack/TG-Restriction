"""Channel search, connection, and analysis"""
from typing import Optional, List, Dict
from pyrogram import Client
from pyrogram.types import Chat
from pyrogram.errors import UsernameNotOccupied, ChannelInvalid
from utils.logger import logger
from core.filters import detect_content_type, ContentType


class ChannelManager:
    """Manages source/destination channel connections and analysis"""
    
    def __init__(self):
        self.source_chat: Optional[Chat] = None
        self.destination_chat: Optional[Chat] = None
        self.last_analysis: Optional[Dict] = None
        
        # Pending search results (for user to select)
        self.pending_search_results: List[Chat] = []
        self.pending_search_type: Optional[str] = None  # "source" or "destination"
    
    async def search_channels(self, client: Client, query: str) -> List[Chat]:
        """
        Search for channels/groups by name or username.
        Uses userbot's dialogs + global search.
        """
        results: List[Chat] = []
        seen_ids = set()
        
        query_clean = query.strip().lstrip("@").lower()
        
        # If it looks like a username or link, try direct resolve
        if query.startswith("@") or query.startswith("https://t.me/") or query.startswith("t.me/"):
            username = query.replace("https://t.me/", "").replace("t.me/", "").lstrip("@")
            try:
                chat = await client.get_chat(username)
                if chat.id not in seen_ids:
                    results.append(chat)
                    seen_ids.add(chat.id)
                return results
            except Exception as e:
                logger.warning(f"Direct resolve failed for {username}: {e}")
        
        # Search in user's dialogs
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
            logger.error(f"Dialog search failed: {e}")
        
        # Global search
        try:
            async for chat in client.search_global(query, limit=10):
                if hasattr(chat, "chat") and chat.chat:
                    c = chat.chat
                    if c.type.name in ("CHANNEL", "SUPERGROUP", "GROUP"):
                        if c.id not in seen_ids:
                            results.append(c)
                            seen_ids.add(c.id)
        except Exception as e:
            logger.debug(f"Global search info: {e}")
        
        return results[:10]  # Limit to 10 results
    
    def set_source(self, chat: Chat):
        """Set the source channel"""
        self.source_chat = chat
        self.last_analysis = None  # Reset analysis on new source
    
    def set_destination(self, chat: Chat):
        """Set the destination channel"""
        self.destination_chat = chat
    
    def clear_source(self):
        self.source_chat = None
        self.last_analysis = None
    
    def clear_destination(self):
        self.destination_chat = None
    
    async def analyze_channel(self, client: Client, limit: int = 500) -> Dict:
        """
        Analyze the source channel content.
        Counts messages by type.
        """
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
            "analyzed_upto": 0,
        }
        
        try:
            async for msg in client.get_chat_history(self.source_chat.id, limit=limit):
                counts["total"] += 1
                counts["analyzed_upto"] = max(counts["analyzed_upto"], msg.id)
                
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
                elif ctype == ContentType.STICKER:
                    counts["sticker"] += 1
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
        """Format the analysis result as a readable message"""
        return (
            f"📊 **Channel Analysis**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎬 Videos: `{analysis.get('video', 0)}`\n"
            f"📄 PDFs: `{analysis.get('pdf', 0)}`\n"
            f"📁 Documents: `{analysis.get('document', 0)}`\n"
            f"🖼 Photos: `{analysis.get('photo', 0)}`\n"
            f"🎵 Audio: `{analysis.get('audio', 0)}`\n"
            f"🎤 Voice: `{analysis.get('voice', 0)}`\n"
            f"🎞 GIFs: `{analysis.get('animation', 0)}`\n"
            f"📝 Text: `{analysis.get('text', 0)}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Total Messages: `{analysis.get('total', 0)}`\n"
            f"📁 Total Files: `{analysis.get('total_files', 0)}`\n\n"
            f"**What to copy?**\n"
            f"• `/v <range>` - Only videos\n"
            f"• `/p <range>` - Only PDFs\n"
            f"• `/d <range>` - Only documents\n"
            f"• `/a <range>` - All content\n"
            f"• `/copy <range>` - Copy everything\n\n"
            f"Example: `/copy 1-50` or `/v 1-100`"
        )
    
    def get_status(self) -> str:
        """Get current channel connection status"""
        source_info = "❌ Not connected"
        if self.source_chat:
            source_info = f"✅ {self.source_chat.title}"
            if self.source_chat.username:
                source_info += f" (@{self.source_chat.username})"
        
        dest_info = "❌ Not set"
        if self.destination_chat:
            dest_info = f"✅ {self.destination_chat.title}"
            if self.destination_chat.username:
                dest_info += f" (@{self.destination_chat.username})"
        
        return (
            f"🔗 **Channel Status**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📥 Source: {source_info}\n"
            f"📤 Destination: {dest_info}"
        )


# Global instance
channel_mgr = ChannelManager()
