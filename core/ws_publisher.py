"""WebSocket trigger publisher for the Cloudflare Worker hub."""
import logging
import uuid
from functools import partial
from typing import Optional
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

import requests

logger = logging.getLogger("ws_publisher")

# Tracking params to strip from product URLs before publishing
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "ref", "refid", "gclid", "fbclid",
}


def normalize_link(url: str) -> str:
    """Strip hash, tracking params, and trailing slash from a URL."""
    if not url:
        return url
    p = urlparse(url)
    qs = {k: v for k, v in parse_qs(p.query, keep_blank_values=True).items()
          if k.lower() not in _TRACKING_PARAMS}
    return urlunparse((
        p.scheme, p.netloc,
        p.path.rstrip("/"),
        p.params,
        urlencode(qs, doseq=True),
        "",          # strip fragment / hash
    ))


def publish_trigger(
    endpoint: str,
    token: str,
    platform: str,
    sku: Optional[str] = None,
    link: Optional[str] = None,
    ttl_seconds: int = 30,
) -> bool:
    """
    POST a trigger payload to the WebSocket hub worker.

    At least one of sku or link must be provided.
    Returns True on HTTP 200, False otherwise.
    """
    if not endpoint or not token:
        logger.error("publish_trigger: endpoint or token not configured")
        return False
    if not sku and not link:
        logger.error("publish_trigger: must supply at least one of sku or link")
        return False

    event_id = str(uuid.uuid4())
    payload: dict = {
        "eventId": event_id,
        "platform": platform,
        "ttlSeconds": ttl_seconds,
    }
    if sku:
        payload["sku"] = str(sku)
    if link:
        payload["link"] = normalize_link(link)

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        if response.status_code == 200:
            logger.error(
                "WS trigger sent OK — eventId=%s platform=%s sku=%s link=%s",
                event_id, platform, sku, payload.get("link"),
            )
            return True
        else:
            logger.error(
                "WS trigger non-200 — status=%d body=%.200s eventId=%s",
                response.status_code, response.text, event_id,
            )
            return False
    except Exception as exc:
        logger.error("WS trigger network failure — %s", exc, exc_info=True)
        return False
