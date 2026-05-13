"""Runtime service manager shared by the web UI."""
import base64
import json
import logging
import threading
from collections import deque
from datetime import datetime
from typing import Any

from core.bot import DiscordBot
from core.database import Database
from core.hv_monitor import HVMonitor
from core.runtime_paths import get_data_dir, get_data_path, get_db_path
from core.shopify_monitor import ShopifyMonitor


class RuntimeLogHandler(logging.Handler):
    """Push stdlib log records into the web recent-log buffer."""

    def __init__(self, manager: "ServiceManager"):
        super().__init__()
        self.manager = manager

    def emit(self, record: logging.LogRecord):
        self.manager.add_log(self.format(record))


class ServiceManager:
    """Owns monitor instances and web-safe operations around them."""

    def __init__(self):
        self.db = Database(get_db_path())
        self.logs = deque(maxlen=500)
        self.lock = threading.RLock()
        self._bot_thread = None
        self.bot = DiscordBot(self.db.get_config("bot_token", ""), self.db)
        self.hv_monitor = HVMonitor(
            self.db,
            log_callback=self.add_log,
            app=self,
            data_dir=get_data_path("hv_monitor_data"),
        )
        self.shopify_monitor = ShopifyMonitor(
            self.db,
            log_callback=self.add_log,
            app=self,
            data_dir=get_data_path("shopify_monitor_data"),
        )
        self.reload_config()
        handler = RuntimeLogHandler(self)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)

    @property
    def proxies(self) -> list[str]:
        return self._lines(self.db.get_config("proxies", ""))

    def add_log(self, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.lock:
            self.logs.appendleft({"time": timestamp, "message": str(message)})

    def get_logs(self, limit: int = 80) -> list[dict[str, str]]:
        with self.lock:
            return list(self.logs)[:limit]

    def reload_config(self):
        self.bot.token = self.db.get_config("bot_token", "")
        self.bot.source_channel_id = self._int_or_none(self.db.get_config("source_channel_id", ""))
        self.bot.target_channel_id = self._int_or_none(self.db.get_config("target_channel_id", ""))
        self.bot.checkouts_channel_id = self._int_or_none(self.db.get_config("checkouts_channel_id", ""))
        self.bot.checkouts_target_channel_id = self._int_or_none(self.db.get_config("checkouts_target_channel_id", ""))
        self.bot.admin_channel_id = self._int_or_none(self.db.get_config("admin_channel_id", ""))
        self.bot.enable_ping = self._bool(self.db.get_config("enable_ping", "false"))
        self.hv_monitor.load_config()
        self.hv_monitor.load_products()
        self.hv_monitor.load_metadata()
        self.hv_monitor.load_stock_status()
        self.shopify_monitor.load_config()
        if self.shopify_monitor.tracker:
            self.shopify_monitor.tracker.load()
        self.add_log("Configuration reloaded")

    def status(self) -> dict[str, Any]:
        return {
            "bot": {"running": self.bot.is_running(), "token_configured": bool(self.bot.token)},
            "hv": self.hv_monitor.get_status(),
            "shopify": self.shopify_monitor.get_status(),
            "data_dir": str(get_data_dir()),
            "db_path": self.db.db_path,
        }

    def control_service(self, service: str, action: str):
        if service == "bot":
            if action == "start":
                if not self.bot.is_running():
                    self.reload_config()
                    self._bot_thread = self.bot.start()
                    self.add_log("Discord bot start requested")
            elif action == "stop":
                self.bot.stop_sync()
                self.add_log("Discord bot stop requested")
            else:
                raise ValueError("Unknown action")
        elif service == "hv":
            getattr(self.hv_monitor, action)()
        elif service == "shopify":
            getattr(self.shopify_monitor, action)()
        else:
            raise ValueError("Unknown service")

    def get_basic_settings(self) -> dict[str, str]:
        keys = [
            "bot_token", "source_channel_id", "target_channel_id",
            "checkouts_channel_id", "checkouts_target_channel_id", "admin_channel_id",
            "enable_ping", "debug_logging", "footer_icon_url", "duplicate_timeout",
            "ws_trigger_url", "ws_trigger_token", "google_sheets_id", "proxies",
        ]
        return {key: self.db.get_config(key, "") for key in keys}

    def update_basic_settings(self, form):
        for key in [
            "bot_token", "source_channel_id", "target_channel_id",
            "checkouts_channel_id", "checkouts_target_channel_id", "admin_channel_id",
            "footer_icon_url", "duplicate_timeout", "ws_trigger_url",
            "ws_trigger_token", "google_sheets_id", "proxies",
        ]:
            self.db.set_config(key, form.get(key, "").strip())
        self.db.set_config("enable_ping", "true" if form.get("enable_ping") else "false")
        self.db.set_config("debug_logging", "true" if form.get("debug_logging") else "false")
        self.reload_config()

    def get_shopify_settings(self) -> dict[str, Any]:
        sm = self.shopify_monitor
        return {
            "main_webhook": sm.main_webhook,
            "singles_webhook": sm.singles_webhook,
            "ignore_singles": sm.ignore_singles,
            "ping_role_id": sm.ping_role_id,
            "ping_enabled": sm.ping_enabled,
            "max_pages": sm.max_pages,
            "check_interval": sm.check_interval,
            "request_timeout": sm.request_timeout,
            "max_workers": sm.max_workers,
            "max_retries": sm.max_retries,
            "webhook_delay": sm.webhook_delay,
            "detailed_logging": sm.detailed_logging,
            "auto_start": sm.auto_start,
            "data_collection_mode": sm.data_collection_mode,
            "stores": "\n".join(sm.stores),
            "keywords": "\n".join(sm.keywords),
        }

    def update_shopify_settings(self, form):
        sm = self.shopify_monitor
        sm.main_webhook = form.get("main_webhook", "").strip()
        sm.singles_webhook = form.get("singles_webhook", "").strip()
        sm.ignore_singles = self._form_bool(form, "ignore_singles")
        sm.ping_role_id = form.get("ping_role_id", "").strip()
        sm.ping_enabled = self._form_bool(form, "ping_enabled")
        sm.max_pages = self._form_int(form, "max_pages", 3)
        sm.check_interval = self._form_int(form, "check_interval", 300)
        sm.request_timeout = self._form_int(form, "request_timeout", 15)
        sm.max_workers = self._form_int(form, "max_workers", 3)
        sm.max_retries = self._form_int(form, "max_retries", 3)
        sm.webhook_delay = self._form_float(form, "webhook_delay", 0.8)
        sm.detailed_logging = self._form_bool(form, "detailed_logging")
        sm.auto_start = self._form_bool(form, "auto_start")
        sm.data_collection_mode = self._form_bool(form, "data_collection_mode")
        sm.stores = self._lines(form.get("stores", ""))
        sm.keywords = [line.lower() for line in self._lines(form.get("keywords", ""))]
        sm.save_config()
        self.add_log("Shopify settings saved")

    def clear_shopify_tracker(self):
        self.shopify_monitor.tracker.clear()
        self.shopify_monitor.tracker.save()
        self.add_log("Shopify tracker cleared")

    def reload_shopify_tracker(self):
        self.shopify_monitor.reload_data()
        self.shopify_monitor.tracker.load()
        self.add_log("Shopify tracker reloaded")

    def get_shopify_variants(self, search: str = "", stock: str = "all") -> list[dict[str, Any]]:
        search = search.lower().strip()
        rows = []
        data = self.shopify_monitor.tracker.data if self.shopify_monitor.tracker else {}
        for store, products in data.items():
            for product_id, variants in products.items():
                title = variants.get("_product_title", product_id)
                keywords = ", ".join(variants.get("_keywords", []))
                for variant_id, variant in variants.items():
                    if variant_id.startswith("_"):
                        continue
                    available = bool(variant.get("available"))
                    if stock == "in" and not available:
                        continue
                    if stock == "out" and available:
                        continue
                    haystack = f"{store} {title} {variant_id} {keywords}".lower()
                    if search and search not in haystack:
                        continue
                    rows.append({
                        "key": self._encode_variant_key(store, product_id, variant_id),
                        "store": store,
                        "product_id": product_id,
                        "variant_id": variant_id,
                        "title": title,
                        "keywords": keywords,
                        "price": variant.get("price", ""),
                        "available": available,
                        "last_seen": variant.get("last_seen", ""),
                    })
        return rows

    def reset_shopify_variants(self, keys: list[str]):
        data = self.shopify_monitor.tracker.data
        count = 0
        for key in keys:
            store, product_id, variant_id = self._decode_variant_key(key)
            variant = data.get(store, {}).get(product_id, {}).get(variant_id)
            if isinstance(variant, dict):
                variant["available"] = False
                count += 1
        self.shopify_monitor.tracker.save()
        self.add_log(f"Reset {count} Shopify variant stock statuses")

    def get_hv_settings(self) -> dict[str, Any]:
        hv = self.hv_monitor
        return {
            "store_url": hv.store_url,
            "token": hv.token,
            "webhook_url": hv.webhook_url,
            "role_id": hv.role_id,
            "ping_enabled": hv.ping_enabled,
            "check_interval": hv.check_interval,
            "auto_start": hv.auto_start,
        }

    def update_hv_settings(self, form):
        hv = self.hv_monitor
        hv.store_url = form.get("store_url", "").strip()
        hv.token = form.get("token", "").strip()
        hv.webhook_url = form.get("webhook_url", "").strip()
        hv.role_id = form.get("role_id", "").strip()
        hv.ping_enabled = self._form_bool(form, "ping_enabled")
        hv.check_interval = self._form_int(form, "check_interval", 30)
        hv.auto_start = self._form_bool(form, "auto_start")
        hv.save_config()
        self.add_log("HV settings saved")

    def get_hv_products(self) -> list[dict[str, Any]]:
        rows = []
        for product_id, ping in self.hv_monitor.products:
            meta = self.hv_monitor.metadata.get(product_id, {})
            rows.append({
                "key": self._encode_text_key(product_id),
                "id": product_id,
                "title": meta.get("title", product_id),
                "type": meta.get("type", ""),
                "price": meta.get("price", ""),
                "ping": ping,
                "known_stock": self.hv_monitor.stock_status.get(product_id),
            })
        return rows

    def add_hv_product_by_id(self, product_id: str, ping: bool):
        product_id = product_id.strip()
        if not product_id:
            return
        self.hv_monitor.add_product(product_id, ping)
        self.add_log(f"HV product added: {product_id}")

    def remove_hv_products(self, keys: list[str]):
        for key in keys:
            self.hv_monitor.remove_product(self._decode_text_key(key))

    def toggle_hv_product_pings(self, keys: list[str]):
        for key in keys:
            self.hv_monitor.toggle_product_ping(self._decode_text_key(key))

    def reset_hv_stock(self, keys: list[str]):
        for key in keys:
            self.hv_monitor.reset_stock_status(self._decode_text_key(key))
        self.hv_monitor.save_stock_status()

    def search_hv_products(self, keyword: str) -> list[dict[str, Any]]:
        results = []
        for product in self.hv_monitor.search_products(keyword):
            image_edges = product.get("images", {}).get("edges", [])
            image = image_edges[0]["node"].get("src") if image_edges else ""
            results.append({
                "key": self._encode_text_key(product.get("id", "")),
                "id": product.get("id", ""),
                "title": product.get("title", ""),
                "type": "product",
                "price": "",
                "image": image,
            })
            for edge in product.get("variants", {}).get("edges", []):
                variant = edge.get("node", {})
                price = variant.get("price", {})
                results.append({
                    "key": self._encode_text_key(variant.get("id", "")),
                    "id": variant.get("id", ""),
                    "title": f"{product.get('title', '')} - {variant.get('title', '')}",
                    "type": "variant",
                    "price": f"{price.get('amount', '')} {price.get('currencyCode', '')}".strip(),
                    "image": image,
                })
        return results

    def add_hv_search_results(self, keys: list[str], results_json: str, ping: bool):
        by_id = {item["id"]: item for item in json.loads(results_json or "[]")}
        for key in keys:
            product_id = self._decode_text_key(key)
            item = by_id.get(product_id, {"title": product_id, "type": "unknown"})
            self.hv_monitor.add_product(product_id, ping, item)

    @staticmethod
    def _lines(value: str) -> list[str]:
        return [line.strip() for line in str(value or "").splitlines() if line.strip()]

    @staticmethod
    def _bool(value: str) -> bool:
        return str(value).lower() in {"true", "1", "yes", "on"}

    @staticmethod
    def _int_or_none(value: str):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _form_bool(form, key: str) -> bool:
        return form.get(key) in {"on", "true", "1", "yes"}

    @staticmethod
    def _form_int(form, key: str, default: int) -> int:
        try:
            return int(form.get(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _form_float(form, key: str, default: float) -> float:
        try:
            return float(form.get(key, default))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _encode_variant_key(store: str, product_id: str, variant_id: str) -> str:
        payload = json.dumps([store, product_id, variant_id])
        return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")

    @staticmethod
    def _decode_variant_key(key: str) -> tuple[str, str, str]:
        payload = base64.urlsafe_b64decode(key.encode("ascii")).decode("utf-8")
        return tuple(json.loads(payload))

    @staticmethod
    def _encode_text_key(value: str) -> str:
        return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")

    @staticmethod
    def _decode_text_key(value: str) -> str:
        return base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
