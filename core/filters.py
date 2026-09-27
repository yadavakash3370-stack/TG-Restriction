"""Content type filters"""
from enum import Enum
from pyrogram.types import Message


class ContentType(Enum):
    VIDEO = "video"
    PDF = "pdf"
    DOCUMENT = "document"
    PHOTO = "photo"
    AUDIO = "audio"
    VOICE = "voice"
    STICKER = "sticker"
    ANIMATION = "animation"
    TEXT = "text"
    OTHER = "other"


def detect_content_type(message: Message) -> ContentType:
    """Detect the primary content type of a message"""
    if message.video:
        return ContentType.VIDEO
    if message.document:
        # Check if it's a PDF
        mime = getattr(message.document, "mime_type", "") or ""
        file_name = getattr(message.document, "file_name", "") or ""
        if "pdf" in mime.lower() or file_name.lower().endswith(".pdf"):
            return ContentType.PDF
        return ContentType.DOCUMENT
    if message.photo:
        return ContentType.PHOTO
    if message.audio:
        return ContentType.AUDIO
    if message.voice:
        return ContentType.VOICE
    if message.sticker:
        return ContentType.STICKER
    if message.animation:
        return ContentType.ANIMATION
    if message.text:
        return ContentType.TEXT
    return ContentType.OTHER


def get_file_size(message: Message) -> int:
    """Get file size from a message"""
    if message.video:
        return getattr(message.video, "file_size", 0) or 0
    if message.document:
        return getattr(message.document, "file_size", 0) or 0
    if message.audio:
        return getattr(message.audio, "file_size", 0) or 0
    if message.voice:
        return getattr(message.voice, "file_size", 0) or 0
    if message.animation:
        return getattr(message.animation, "file_size", 0) or 0
    if message.photo:
        return getattr(message.photo, "file_size", 0) or 0
    return 0


def matches_filter(message: Message, filter_type: str) -> bool:
    """Check if a message matches a given filter"""
    content_type = detect_content_type(message)
    
    filter_type = filter_type.lower()
    
    if filter_type in ("all", "a"):
        return content_type != ContentType.OTHER
    if filter_type in ("video", "v"):
        return content_type == ContentType.VIDEO
    if filter_type in ("pdf", "p"):
        return content_type == ContentType.PDF
    if filter_type in ("document", "doc", "d"):
        return content_type in (ContentType.DOCUMENT, ContentType.PDF)
    
    return False
