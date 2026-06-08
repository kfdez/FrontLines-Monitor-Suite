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


def _stock_monitor(stock_status, response):
    monitor = object.__new__(HVMonitor)
    monitor.stock_status = stock_status
    monitor.metadata = {}
    monitor._pending_stock_resets = set()
    monitor._graphql_request = Mock(return_value=response)
    monitor.save_metadata = Mock()
    monitor.ui_refresh_callback = None
    monitor._send_notification = Mock()
    monitor.log = Mock()
    return monitor


def test_reset_stock_status_only_queues_selected_product():
    monitor = _stock_monitor(
        {
            "gid://shopify/ProductVariant/1": True,
            "gid://shopify/ProductVariant/2": True,
        },
        {},
    )

    monitor.reset_stock_status("gid://shopify/Product/1")

    assert monitor.stock_status == {
        "gid://shopify/ProductVariant/1": True,
        "gid://shopify/ProductVariant/2": True,
    }
    assert monitor._pending_stock_resets == {"gid://shopify/Product/1"}


def test_selected_product_reset_forces_only_its_next_notification():
    product_id = "gid://shopify/Product/1"
    variant_id = "gid://shopify/ProductVariant/1"
    response = {
        "data": {
            "node": {
                "id": product_id,
                "title": "Selected Product",
                "onlineStoreUrl": "https://example.com/selected",
                "images": {"edges": []},
                "variants": {
                    "edges": [
                        {
                            "node": {
                                "id": variant_id,
                                "title": "Default",
                                "availableForSale": True,
                                "price": {
                                    "amount": "10.00",
                                    "currencyCode": "CAD",
                                },
                            }
                        }
                    ]
                },
            }
        }
    }
    monitor = _stock_monitor({variant_id: True}, response)
    monitor.reset_stock_status(product_id)
    current_status = {}

    monitor._check_product(product_id, True, current_status)

    monitor._send_notification.assert_called_once()
    assert current_status == {variant_id: True}
    assert product_id not in monitor._pending_stock_resets


def test_failed_selected_product_check_keeps_reset_queued():
    product_id = "gid://shopify/Product/1"
    monitor = _stock_monitor({}, None)
    monitor.reset_stock_status(product_id)

    monitor._check_product(product_id, True, {})

    assert monitor._pending_stock_resets == {product_id}
    monitor._send_notification.assert_not_called()
