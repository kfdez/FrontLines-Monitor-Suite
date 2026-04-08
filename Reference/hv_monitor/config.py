"""
HV Monitor Configuration
"""

from dataclasses import dataclass
from frontlines.core.base_config import BaseModuleConfig


@dataclass
class HVMonitorConfig(BaseModuleConfig):
    """Configuration for the HV Monitor module."""

    # Shopify API
    store_url: str = "https://redtrainer.myshopify.com/api/2024-07/graphql.json"
    token: str = ""

    # Discord
    discord_webhook: str = ""
    discord_role_id: str = ""
    ping_role: bool = False
    rate_limit_delay: float = 1.0

    # Monitoring
    check_interval: int = 30
    search_limit: int = 10
