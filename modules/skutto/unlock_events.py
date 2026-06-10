"""Detection helpers for PokemonCenter module status messages."""
import re
import time
from typing import Any, Iterable


POKEMONCENTER_ROLE_MENTION = "<@&1385619239309672488>"
POKEMONCENTER_STORE_URL = "https://www.pokemoncenter.com/en-ca/"
MODULE_STATUS_DUPLICATE_TIMEOUT = 60


def _embed_text(embed: Any) -> str:
    embed_dict = embed.to_dict()
    parts = [
        embed_dict.get("title", ""),
        embed_dict.get("description", ""),
        embed_dict.get("url", ""),
        embed_dict.get("author", {}).get("name", ""),
        embed_dict.get("footer", {}).get("text", ""),
    ]
    for field in embed_dict.get("fields", []):
        parts.extend((field.get("name", ""), field.get("value", "")))
    return "\n".join(str(part) for part in parts if part)


def get_pokemoncenter_module_status(content: str, embeds: Iterable[Any]) -> str | None:
    """Return locked/unlocked for flexible PokemonCenter module status messages."""
    text = "\n".join([content or "", *(_embed_text(embed) for embed in embeds)])
    normalized = re.sub(r"[^a-z0-9]+", "", text.lower())
    if "pokemoncenter" not in normalized or "module" not in normalized:
        return None
    if "unlock" in normalized:
        return "unlocked"
    if "locked" in normalized:
        return "locked"
    return None


def reserve_module_status_event(
    recent_events: dict[str, float],
    status: str,
    now: float | None = None,
) -> bool:
    """Reserve the event before the caller performs any await."""
    current = time.monotonic() if now is None else now
    event_key = f"event:pokemoncenter:module-{status}"
    last_seen = recent_events.get(event_key, 0)
    if current - last_seen < MODULE_STATUS_DUPLICATE_TIMEOUT:
        return False
    recent_events[event_key] = current
    return True
