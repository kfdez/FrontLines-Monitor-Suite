from unittest.mock import Mock, patch

import pytest

from core.hv_monitor import HVMonitor


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("123456789012345678", "123456789012345678"),
        (" <@&123456789012345678> ", "123456789012345678"),
        ("@role", ""),
        ("<@123456789012345678>", ""),
        ("", ""),
    ],
)
def test_normalize_role_id(value, expected):
    assert HVMonitor._normalize_role_id(value) == expected


def _monitor(role_id="123456789012345678", ping_enabled=True):
    monitor = object.__new__(HVMonitor)
    monitor.webhook_url = "https://discord.com/api/webhooks/test"
    monitor.role_id = role_id
    monitor.ping_enabled = ping_enabled
    monitor.log = Mock()
    return monitor


def _product():
    return {
        "id": "gid://shopify/Product/1",
        "title": "Test Product",
        "onlineStoreUrl": "https://example.com/product",
        "images": {"edges": []},
    }


@patch("core.hv_monitor.requests.post")
def test_product_ping_sends_role_mention(post):
    post.return_value.raise_for_status.return_value = None
    monitor = _monitor(role_id="<@&123456789012345678>")

    monitor._send_notification(_product(), None, ping_override=True)

    payload = post.call_args.kwargs["json"]
    assert payload["content"] == "<@&123456789012345678>"
    assert payload["allowed_mentions"] == {
        "parse": [],
        "roles": ["123456789012345678"],
    }


@pytest.mark.parametrize(
    ("ping_enabled", "product_ping"),
    [
        (False, True),
        (True, False),
    ],
)
@patch("core.hv_monitor.requests.post")
def test_both_ping_switches_are_required(post, ping_enabled, product_ping):
    post.return_value.raise_for_status.return_value = None
    monitor = _monitor(ping_enabled=ping_enabled)

    monitor._send_notification(_product(), None, ping_override=product_ping)

    payload = post.call_args.kwargs["json"]
    assert "content" not in payload
    assert "allowed_mentions" not in payload


@patch("core.hv_monitor.requests.post")
def test_invalid_role_value_does_not_send_malformed_mention(post):
    post.return_value.raise_for_status.return_value = None
    monitor = _monitor(role_id="Stock Alerts")

    monitor._send_notification(_product(), None, ping_override=True)

    payload = post.call_args.kwargs["json"]
    assert "content" not in payload
    assert "allowed_mentions" not in payload
