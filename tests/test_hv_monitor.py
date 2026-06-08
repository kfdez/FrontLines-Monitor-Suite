import tempfile
import unittest
from unittest.mock import patch

from core.hv_monitor import HVMonitor


class FakeDatabase:
    def get_config(self, key, default=""):
        return default

    def set_config(self, key, value):
        pass


class FakeResponse:
    def raise_for_status(self):
        pass


class HVMonitorRoleMentionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.monitor = HVMonitor(FakeDatabase(), data_dir=self.temp_dir.name)
        self.monitor.webhook_url = "https://discord.test/webhook"
        self.monitor.role_id = "123456789012345678"
        self.product = {
            "id": "gid://shopify/Product/1",
            "title": "Test Product",
            "onlineStoreUrl": "https://example.test/products/test",
            "images": {"edges": []},
        }
        self.variant = {
            "id": "gid://shopify/ProductVariant/2",
            "title": "Default",
            "price": {"amount": "10.00", "currencyCode": "CAD"},
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("core.hv_monitor.requests.post", return_value=FakeResponse())
    def test_product_ping_mentions_role_without_global_ping(self, post):
        self.monitor.ping_enabled = False

        self.monitor._send_notification(self.product, self.variant, ping_override=True)

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["content"], "<@&123456789012345678>")
        self.assertEqual(
            payload["allowed_mentions"],
            {"parse": [], "roles": ["123456789012345678"]},
        )

    @patch("core.hv_monitor.requests.post", return_value=FakeResponse())
    def test_role_mention_input_is_normalized(self, post):
        self.monitor.role_id = "<@&123456789012345678>"

        self.monitor._send_notification(self.product, self.variant, ping_override=True)

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["content"], "<@&123456789012345678>")

    @patch("core.hv_monitor.requests.post", return_value=FakeResponse())
    def test_disabled_product_does_not_ping_when_global_ping_is_off(self, post):
        self.monitor.ping_enabled = False

        self.monitor._send_notification(self.product, self.variant, ping_override=False)

        payload = post.call_args.kwargs["json"]
        self.assertNotIn("content", payload)
        self.assertNotIn("allowed_mentions", payload)


if __name__ == "__main__":
    unittest.main()
