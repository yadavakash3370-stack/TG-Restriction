"""Bandwidth tracker with file persistence"""
import json
import os
from config import BANDWIDTH_LIMIT_BYTES, BANDWIDTH_LIMIT_GB, BANDWIDTH_FILE
from utils.progress import format_bytes


class BandwidthTracker:
    def __init__(self):
        self.bytes_used: int = 0
        self.limit_bytes: int = BANDWIDTH_LIMIT_BYTES
        self.limit_gb: float = BANDWIDTH_LIMIT_GB

    def save_to_file(self):
        try:
            with open(BANDWIDTH_FILE, "w") as f:
                json.dump({"bytes_used": self.bytes_used}, f)
        except Exception:
            pass

    def load_from_file(self):
        try:
            if os.path.exists(BANDWIDTH_FILE):
                with open(BANDWIDTH_FILE, "r") as f:
                    data = json.load(f)
                self.bytes_used = data.get("bytes_used", 0)
        except Exception:
            pass

    def add_usage(self, bytes_count: int):
        self.bytes_used += bytes_count
        self.save_to_file()

    def can_download(self) -> bool:
        return self.bytes_used < self.limit_bytes

    def get_remaining_bytes(self) -> int:
        return max(0, self.limit_bytes - self.bytes_used)

    def get_percentage(self) -> float:
        if self.limit_bytes == 0:
            return 0
        return (self.bytes_used / self.limit_bytes) * 100

    def reset(self):
        self.bytes_used = 0
        self.save_to_file()

    def set_limit(self, gb: float):
        self.limit_gb = gb
        self.limit_bytes = int(gb * 1024 * 1024 * 1024)

    def get_mode(self) -> str:
        return "🔴 COPY-ONLY" if not self.can_download() else "🟢 NORMAL"

    def format_status(self) -> str:
        pct = self.get_percentage()
        filled = int(20 * pct / 100)
        bar = "█" * filled + "░" * (20 - filled)
        return (
            f"📊 **Bandwidth**\n"
            f"Used: `{format_bytes(self.bytes_used)}` / `{self.limit_gb} GB`\n"
            f"`[{bar}] {pct:.1f}%`\n"
            f"Mode: {self.get_mode()}"
        )


bandwidth = BandwidthTracker()
