"""
Stock Scraper Configuration
"""

from dataclasses import dataclass
from frontlines.core.base_config import BaseModuleConfig


@dataclass
class StockScraperConfig(BaseModuleConfig):
    """Configuration for the Stock Scraper module."""

    # Discord webhooks
    main_webhook: str = ""
    singles_webhook: str = ""
    ignore_singles: bool = False  # If True, don't send singles at all

    # Scraping settings
    max_pages: int = 3
    check_interval: int = 300  # seconds
    request_timeout: int = 15
    max_workers: int = 3  # Concurrent store checks
    max_retries: int = 3  # Retries per request

    # Rate limiting
    webhook_delay: float = 0.8

    # Logging
    detailed_logging: bool = False  # Show verbose scanning details
