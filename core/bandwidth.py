"""Bandwidth tracking system (in-memory, resets on restart)"""
from config import BANDWIDTH_LIMIT_BYTES, BANDWIDTH_LIMIT_GB
from utils.progress import format_bytes


class BandwidthTracker:
    """Tracks bandwidth usage across the bot lifetime"""
    
    def __init__(self):
        self.bytes_used: int = 0
        self.limit_bytes: int = BANDWIDTH_LIMIT_BYTES
        self.limit_gb: float = BANDWIDTH_LIMIT_GB
    
    def add_usage(self, bytes_count: int):
        """Add bytes to usage counter"""
        self.bytes_used += bytes_count
    
    def can_download(self) -> bool:
        """Check if download+upload mode is still allowed"""
        return self.bytes_used < self.limit_bytes
    
    def get_usage_bytes(self) -> int:
        return self.bytes_used
    
    def get_remaining_bytes(self) -> int:
        return max(0, self.limit_bytes - self.bytes_used)
    
    def get_percentage(self) -> float:
        if self.limit_bytes == 0:
            return 0
        return (self.bytes_used / self.limit_bytes) * 100
    
    def reset(self):
        """Reset the bandwidth counter"""
        self.bytes_used = 0
    
    def set_limit(self, gb: float):
        """Update the bandwidth limit"""
        self.limit_gb = gb
        self.limit_bytes = int(gb * 1024 * 1024 * 1024)
    
    def get_mode(self) -> str:
        """Get current operating mode"""
        return "🔴 COPY-ONLY" if not self.can_download() else "🟢 NORMAL"
    
    def format_status(self) -> str:
        """Format bandwidth status message"""
        percentage = self.get_percentage()
        bar_length = 20
        filled = int(bar_length * percentage / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        return (
            f"📊 **Bandwidth Status**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Used: `{format_bytes(self.bytes_used)}` / `{self.limit_gb} GB`\n"
            f"`[{bar}] {percentage:.1f}%`\n"
            f"Remaining: `{format_bytes(self.get_remaining_bytes())}`\n"
            f"Mode: {self.get_mode()}"
        )


# Global instance
bandwidth = BandwidthTracker()
