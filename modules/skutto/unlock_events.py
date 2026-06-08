"""Detection helpers for module-unlocked checkout messages."""
import re
import time
from typing import Any, Iterable


POKEMONCENTER_UNLOCK_EVENT_KEY = "event:pokemoncenter:module-unlocked"
POKEMONCENTER_ROLE_MENTION = "<@&1385619239309672488>"
UNLOCK_DUPLICATE_TIMEOUT = 60


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


def is_pokemoncenter_module_unlocked(content: str, embeds: Iterable[Any]) -> bool:
    """Match flexible PokemonCenter module-unlocked messages."""
    text = "\n".join([content or "", *(_embed_text(embed) for embed in embeds)])
    normalized = re.sub(r"[^a-z0-9]+", "", text.lower())
    return all(keyword in normalized for keyword in ("pokemoncenter", "module", "unlock"))


def reserve_unlock_event(recent_events: dict[str, float], now: float | None = None) -> bool:
    """Reserve the event before the caller performs any await."""
    current = time.monotonic() if now is None else now
    last_seen = recent_events.get(POKEMONCENTER_UNLOCK_EVENT_KEY, 0)
    if current - last_seen < UNLOCK_DUPLICATE_TIMEOUT:
        return False
    recent_events[POKEMONCENTER_UNLOCK_EVENT_KEY] = current
    return True
