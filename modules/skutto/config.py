"""Skutto module configuration."""
from typing import Dict, Any


class SkuttoConfig:
    """Configuration for the Skutto module."""

    def __init__(self):
        self.platform_map = {
            "walmart": ("walmart", "product"),
            "gamestop": ("gamestop", "product"),
            "amazon": ("amazonv3", "sku"),
            "costco": ("costco", "title/sku"),
            "bestbuy": ("bestbuy", "title/sku"),
            "popmart": ("popmart", "title/sku"),
            "queueit": ("queueit", "Queue Pass"),
            "indigo": ("indigoca", "product"),
        }
        self.duplicate_timeout = 500  # seconds

    def get_platform_info(self, platform: str) -> tuple:
        """Get platform info (key, keyword)."""
        return self.platform_map.get(platform.lower(), (None, None))

    def get_all_platforms(self) -> list:
        """Get list of all supported platforms."""
        return list(self.platform_map.keys())
