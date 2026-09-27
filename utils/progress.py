"""Progress tracking utilities"""
import time
from typing import Optional


class ProgressTracker:
    """Tracks progress of copy operations"""
    
    def __init__(self, total: int = 0):
        self.total = total
        self.current = 0
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.start_time = time.time()
        self.bytes_transferred = 0
        self.current_file: Optional[str] = None
        self.is_paused = False
        self.is_stopped = False
    
    def increment_success(self, bytes_size: int = 0):
        self.current += 1
        self.success += 1
        self.bytes_transferred += bytes_size
    
    def increment_failed(self):
        self.current += 1
        self.failed += 1
    
    def increment_skipped(self):
        self.current += 1
        self.skipped += 1
    
    def get_elapsed_time(self) -> float:
        return time.time() - self.start_time
    
    def get_speed_mbps(self) -> float:
        elapsed = self.get_elapsed_time()
        if elapsed == 0:
            return 0
        mb = self.bytes_transferred / (1024 * 1024)
        return mb / elapsed
    
    def get_eta_seconds(self) -> int:
        if self.current == 0:
            return 0
        elapsed = self.get_elapsed_time()
        rate = self.current / elapsed
        remaining = self.total - self.current
        if rate == 0:
            return 0
        return int(remaining / rate)
    
    def get_percentage(self) -> float:
        if self.total == 0:
            return 0
        return (self.current / self.total) * 100
    
    def format_progress_bar(self, length: int = 20) -> str:
        """Return a text progress bar"""
        if self.total == 0:
            return "[" + "░" * length + "]"
        filled = int(length * self.current / self.total)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"
    
    def format_summary(self) -> str:
        """Return a formatted progress summary"""
        percentage = self.get_percentage()
        bar = self.format_progress_bar()
        eta = self.get_eta_seconds()
        speed = self.get_speed_mbps()
        
        eta_str = f"{eta // 60}m {eta % 60}s" if eta > 60 else f"{eta}s"
        
        return (
            f"{bar} {percentage:.1f}%\n"
            f"📦 Progress: {self.current}/{self.total}\n"
            f"✅ Success: {self.success} | ❌ Failed: {self.failed} | ⏭ Skipped: {self.skipped}\n"
            f"⚡ Speed: {speed:.2f} MB/s\n"
            f"⏱ ETA: {eta_str}"
        )


def format_bytes(size: int) -> str:
    """Format bytes to human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"
