"""Caption handling utilities"""
from config import BOT_SIGNATURE


def build_caption(original_caption: str = None) -> str:
    """
    Build a new caption with the bot signature.
    Keeps original caption and adds signature below.
    """
    if original_caption and original_caption.strip():
        return f"{original_caption}\n\n{BOT_SIGNATURE}"
    return BOT_SIGNATURE


def get_signature_only() -> str:
    """Return only the signature (for media without original caption)"""
    return BOT_SIGNATURE
