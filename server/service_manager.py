"""Runtime service manager shared by the web UI."""
import base64
import asyncio
import csv
import json
import logging
import re
import threading
import time
from collections import deque
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import discord
import requests

from core.bot import DiscordBot
from core.database import Database
from core.hv_monitor import HVMonitor
from core.runtime_paths import get_data_dir, get_data_path, get_db_path
from core.sheets import SheetsManager
from core.shopify_monitor import ShopifyMonitor


SKUTTO_RESTOCK_STRIP_FIELDS = {
    "account",
    "address",
    "billing",
    "card",
    "card number",
    "checkout",
    "checkout url",
    "cookie",
    "cookies",
    "cvv",
    "email",
    "expiration",
    "expiry",
    "mode",
    "monitor",
    "offer id",
    "offerid",
    "order email",
    "order id",
    "order link",
    "password",
    "payment",
    "phone",
    "profile",
    "profile email",
    "proxy",
    "purchase id",
    "session",
    "shipping",
    "task",
    "task group",
    "task id",
    "user agent",
}

SKUTTO_CHECKOUT_STRIP_FIELDS = {
    "account",
    "email",
    "offer id",
    "order email",
    "order id",
    "order link",
    "proxy",
    "purchase id",
}


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
        self.sheets = None
        self.sheets_error = ""
        self.sku_data = {}
        self.skutto_data_dir = Path(get_data_path("skutto_data"))
        self.skutto_products_cache = self.skutto_data_dir / "products_cache.json"
        self.recent_forwards = {}
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
        self.load_skutto_products_cache()
        self.reload_config()
        self.refresh_skutto_products_async()
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
        self.duplicate_timeout = self._form_int({"duplicate_timeout": self.db.get_config("duplicate_timeout", "60")}, "duplicate_timeout", 60)
        self.debug_logging = self._bool(self.db.get_config("debug_logging", "false"))
        self.ws_trigger_url = self.db.get_config("ws_trigger_url", "")
        self.ws_trigger_token = self.db.get_config("ws_trigger_token", "")
        self.bot.refresh_data()
        self.bot.set_sku_data(self.sku_data)
        self.hv_monitor.load_config()
        self.hv_monitor.load_products()
        self.hv_monitor.load_metadata()
        self.hv_monitor.load_stock_status()
        self.shopify_monitor.load_config()
        if self.shopify_monitor.tracker:
            self.shopify_monitor.tracker.load()
        self.add_log("Configuration reloaded")

    def load_skutto_products_cache(self) -> list[dict[str, Any]]:
        if not self.skutto_products_cache.exists():
            return []
        try:
            with self.skutto_products_cache.open("r", encoding="utf-8") as handle:
                products = json.load(handle)
            if not isinstance(products, list):
                raise ValueError("cache root is not a list")
            self.sku_data = {product["sku"]: product for product in products if product.get("sku")}
            self.bot.set_sku_data(self.sku_data)
            self.add_log(f"Loaded {len(self.sku_data)} cached SKUtto products")
            return products
        except Exception as exc:
            self.sheets_error = f"Failed to load SKUtto product cache: {exc}"
            self.add_log(self.sheets_error)
            return []

    def save_skutto_products_cache(self):
        self.skutto_data_dir.mkdir(parents=True, exist_ok=True)
        products = sorted(self.sku_data.values(), key=lambda row: row.get("sku", ""))
        with self.skutto_products_cache.open("w", encoding="utf-8") as handle:
            json.dump(products, handle, indent=2)

    def refresh_skutto_products_async(self):
        def refresh():
            try:
                self.load_skutto_products_from_sheets()
            except Exception as exc:
                self.sheets_error = str(exc)
                self.add_log(f"SKUtto auto-refresh skipped: {exc}")

        thread = threading.Thread(target=refresh, name="skutto-product-refresh", daemon=True)
        thread.start()

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
                    self._prepare_skutto_bot()
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

    def _prepare_skutto_bot(self):
        self.bot.refresh_data()
        if not self.sku_data:
            try:
                self.load_skutto_products_from_sheets()
            except Exception as exc:
                self.add_log(f"SKUtto product load skipped: {exc}")
        self.bot.set_sku_data(self.sku_data)
        self.bot.set_on_ready(self._on_skutto_ready)
        self.bot.set_on_message(self._handle_skutto_message)
        self.bot.set_command_callback(self.add_log)
        self.bot.set_on_email_changed(self._on_email_changed)

    async def _on_skutto_ready(self, bot):
        self.add_log(f"SKUtto bot connected as {bot.user}")
        if self.bot.admin_channel_id:
            channel = bot.get_channel(self.bot.admin_channel_id)
            if channel:
                await channel.send("SKUtto is now online and ready.")

    async def _on_email_changed(self):
        self.bot.refresh_data()
        self.add_log("Email lookup refreshed")

    async def _handle_skutto_message(self, message, bot):
        if message.author.bot and bot.bot and message.author.id == bot.bot.user.id:
            return

        channel_id = int(message.channel.id)
        if self.bot.checkouts_channel_id and channel_id == self.bot.checkouts_channel_id:
            await self._handle_checkout(message, bot)
            return

        if not self.bot.source_channel_id or channel_id != self.bot.source_channel_id:
            return

        if not self.bot.target_channel_id:
            return

        target_channel = bot.bot.get_channel(self.bot.target_channel_id)
        if not target_channel:
            self.add_log("SKUtto target channel not found")
            return

        if message.embeds:
            for embed in message.embeds:
                processed = self._process_skutto_embed(embed)
                title = processed.get("title", "No title")
                matched_sku = processed.get("matched_sku", "")
                if matched_sku:
                    now = time.time()
                    if now - self.recent_forwards.get(matched_sku, 0) < self.duplicate_timeout:
                        self.add_log(f"Skipping duplicate SKU: {matched_sku}")
                        continue

                new_embed = discord.Embed.from_dict(processed)
                role_id = processed.get("role_id", "").strip()
                if self.bot.enable_ping and role_id.isdigit():
                    await target_channel.send(content=f"<@&{role_id}> - {title}")
                await target_channel.send(embed=new_embed)

                if processed.get("ws_enabled"):
                    self._publish_ws_trigger(processed)
                if matched_sku:
                    self.recent_forwards[matched_sku] = time.time()
            self.add_log(f"Forwarded {len(message.embeds)} SKUtto embed(s)")
        elif message.content:
            await target_channel.send(message.content)
            self.add_log("Forwarded SKUtto text message")

    def _process_skutto_embed(self, embed):
        embed_dict = embed.to_dict()
        sku_value = None
        for field in embed_dict.get("fields", []):
            if self._normalize_embed_field_name(field.get("name", "")) in {"sku", "title/sku"}:
                sku_value = field.get("value", "").strip()
                break
        if not sku_value:
            for field in embed_dict.get("fields", []):
                if self._normalize_embed_field_name(field.get("name", "")) in {"title", "product"}:
                    sku_value = field.get("value", "").strip()
                    break

        removed_fields = self._strip_skutto_embed_fields(embed_dict, SKUTTO_RESTOCK_STRIP_FIELDS)
        product = self._find_skutto_product(sku_value)
        if not product:
            if removed_fields and self.debug_logging:
                self.add_log(f"SKUtto stripped fields from unmatched embed: {', '.join(removed_fields)}")
            return embed_dict

        platform = product.get("platform", "unknown")
        embed_dict["title"] = f"[{platform.capitalize()} Restock] - {product.get('name', '')}"
        if product.get("url"):
            embed_dict["url"] = product["url"]
        footer_icon = self.db.get_config("footer_icon_url", "")
        footer = {"text": f"FrontLines - SKUtto - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
        if footer_icon:
            footer["icon_url"] = footer_icon
        embed_dict["footer"] = footer
        embed_dict["role_id"] = product.get("roleid", "")
        embed_dict["matched_sku"] = sku_value
        embed_dict["ws_enabled"] = str(product.get("send_to_websocket", "")).strip().upper() in {"TRUE", "1", "YES"}
        embed_dict["ws_platform"] = platform.lower()
        if removed_fields and self.debug_logging:
            self.add_log(f"SKUtto stripped fields for {sku_value}: {', '.join(removed_fields)}")
        return embed_dict

    def _find_skutto_product(self, value: str):
        if not value:
            return None
        needle = value.upper()
        for product in self.sku_data.values():
            for key in ("sku", "sku2", "name"):
                if str(product.get(key, "")).upper() == needle:
                    return product
        return None

    async def _handle_checkout(self, message, bot):
        emails_found = set()

        def extract_emails(text):
            if not text:
                return set()
            cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
            cleaned = re.sub(r"mailto:", "", cleaned)
            return set(re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", cleaned))

        for embed in message.embeds:
            embed_dict = embed.to_dict()
            for field in embed_dict.get("fields", []):
                emails_found.update(extract_emails(field.get("value", "")))
            emails_found.update(extract_emails(embed.description))
            emails_found.update(extract_emails(embed.title))
        emails_found.update(extract_emails(message.content))

        for index, email in enumerate(emails_found):
            if index:
                await asyncio.sleep(1)
            discord_id = self.bot.email_lookup.get(email.lower())
            if not discord_id:
                self.add_log(f"Checkout email not mapped: {email}")
                continue
            try:
                user = await bot.bot.fetch_user(discord_id)
                for embed in message.embeds:
                    await user.send("Successful Checkout!", embed=embed)
                if not message.embeds:
                    await user.send("Successful Checkout!")
                self.add_log(f"Checkout DM sent to {email}")
            except Exception as exc:
                self.add_log(f"Failed checkout DM for {email}: {exc}")

        if self.bot.checkouts_target_channel_id and message.embeds:
            target_channel = bot.bot.get_channel(self.bot.checkouts_target_channel_id)
            if target_channel:
                for embed in message.embeds:
                    await target_channel.send(embed=discord.Embed.from_dict(self._process_checkout_embed(embed.to_dict())))

    @classmethod
    def _process_checkout_embed(cls, embed_dict: dict) -> dict:
        strip_set = set(SKUTTO_CHECKOUT_STRIP_FIELDS)
        fields = embed_dict.get("fields", [])
        is_amazon = any(
            cls._normalize_embed_field_name(field.get("name", "")) == "site"
            and "amazon" in str(field.get("value", "")).strip().lower()
            for field in fields
        )
        if is_amazon:
            strip_set.remove("email")
        cls._strip_skutto_embed_fields(embed_dict, strip_set)
        return embed_dict

    @staticmethod
    def _normalize_embed_field_name(name: Any) -> str:
        cleaned = str(name or "").replace("||", "").strip().lower()
        return re.sub(r"\s+", " ", cleaned)

    @classmethod
    def _strip_skutto_embed_fields(cls, embed_dict: dict, strip_set: set[str]) -> list[str]:
        removed = []
        cleaned_fields = []
        for field in embed_dict.get("fields", []):
            field_name = cls._normalize_embed_field_name(field.get("name", ""))
            compact_name = field_name.replace(" ", "")
            if field_name in strip_set or compact_name in strip_set:
                removed.append(str(field.get("name", "")).replace("||", "").strip())
                continue

            cleaned = dict(field)
            if "name" in cleaned:
                cleaned["name"] = str(cleaned["name"]).replace("||", "").strip()
            if "value" in cleaned:
                cleaned["value"] = str(cleaned["value"]).replace("||", "").strip()
            if cleaned.get("name") and cleaned.get("value"):
                cleaned_fields.append(cleaned)

        embed_dict["fields"] = cleaned_fields
        return removed

    def _publish_ws_trigger(self, processed: dict):
        if not self.ws_trigger_url or not self.ws_trigger_token:
            self.add_log("WebSocket trigger skipped: URL or token not configured")
            return
        payload = {
            "platform": processed.get("ws_platform", "costco"),
            "sku": processed.get("matched_sku"),
            "link": processed.get("url"),
        }
        headers = {"Authorization": f"Bearer {self.ws_trigger_token}"}
        try:
            response = requests.post(self.ws_trigger_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            self.add_log(f"WebSocket trigger sent for {payload.get('sku')}")
        except Exception as exc:
            self.add_log(f"WebSocket trigger failed: {exc}")

    def _get_sheets(self):
        if self.sheets:
            return self.sheets
        try:
            self.sheets = SheetsManager()
            self.sheets_error = ""
            return self.sheets
        except Exception as exc:
            self.sheets_error = str(exc)
            raise

    def load_skutto_products_from_sheets(self) -> list[dict[str, Any]]:
        spreadsheet_id = self.db.get_config("google_sheets_id", "") or self.db.get_config("spreadsheet_id", "")
        if not spreadsheet_id:
            raise ValueError("Google Sheets ID is not configured")
        products = self._get_sheets().get_products(spreadsheet_id)
        self.sku_data = {product["sku"]: product for product in products if product.get("sku")}
        self.bot.set_sku_data(self.sku_data)
        self.save_skutto_products_cache()
        self.add_log(f"Loaded {len(products)} SKUtto products from Google Sheets")
        return products

    def get_skutto_products(self, search: str = "") -> list[dict[str, Any]]:
        search = search.lower().strip()
        rows = []
        for product in self.sku_data.values():
            haystack = " ".join(str(product.get(key, "")) for key in ("sku", "sku2", "name", "url", "platform", "roleid", "role")).lower()
            if search and search not in haystack:
                continue
            rows.append(product)
        return sorted(rows, key=lambda row: row.get("sku", ""))

    def upsert_skutto_product(self, form):
        sku = form.get("sku", "").strip().upper()
        if not sku:
            raise ValueError("SKU is required")
        product = {
            "sku": sku,
            "sku2": form.get("sku2", "").strip(),
            "name": form.get("name", "").strip(),
            "url": form.get("url", "").strip(),
            "platform": form.get("platform", "").strip(),
            "roleid": form.get("roleid", "").strip(),
            "role": form.get("role", "").strip(),
        }
        old_sku = form.get("old_sku", "").strip().upper()
        current = self.sku_data.get(old_sku or sku, {})
        row_index = current.get("_row")
        spreadsheet_id = self.db.get_config("google_sheets_id", "")
        if spreadsheet_id:
            if row_index:
                self._get_sheets().update_product(
                    spreadsheet_id,
                    int(row_index),
                    product["sku"],
                    product["sku2"],
                    product["name"],
                    product["url"],
                    product["platform"],
                    product["roleid"],
                    product["role"],
                )
            else:
                self._get_sheets().append_product(spreadsheet_id, product["sku"], product["sku2"], product["name"], product["url"], product["platform"], product["roleid"], product["role"])
        if old_sku and old_sku != sku:
            self.sku_data.pop(old_sku, None)
        product["_row"] = row_index
        self.sku_data[sku] = product
        self.bot.set_sku_data(self.sku_data)
        self.save_skutto_products_cache()

    def get_pending_skus(self, status_filter: str = "pending", search: str = "") -> list[dict[str, Any]]:
        rows = self.db.get_all_pending_skus()
        if status_filter and status_filter != "all":
            rows = [row for row in rows if row.get("status") == status_filter]
        search = search.lower().strip()
        if search:
            rows = [
                row for row in rows
                if search in " ".join(str(row.get(key, "")) for key in ("sku", "sku2", "name", "url", "platform", "role_id", "role", "submitted_by")).lower()
            ]
        return rows

    def update_pending_sku(self, sku_id: int, form):
        self.db.update_pending_sku(
            sku_id,
            platform=form.get("platform", "").strip(),
            role_id=form.get("role_id", "").strip(),
            sku2=form.get("sku2", "").strip(),
            role=form.get("role", "").strip(),
        )

    def approve_pending_sku(self, sku_id: int):
        sku_data = self.db.get_sku_by_id(sku_id)
        if not sku_data:
            raise ValueError("Pending SKU not found")
        if not sku_data.get("platform") or not sku_data.get("role_id"):
            raise ValueError("Platform and Role ID are required before approval")
        self.db.approve_sku(sku_id, 0)
        spreadsheet_id = self.db.get_config("google_sheets_id", "")
        if spreadsheet_id:
            self._get_sheets().append_product(
                spreadsheet_id,
                sku_data["sku"],
                sku_data.get("sku2", ""),
                sku_data["name"],
                sku_data.get("url", ""),
                sku_data.get("platform", ""),
                sku_data.get("role_id", ""),
                sku_data.get("role", ""),
            )
        self.sku_data[sku_data["sku"].upper()] = {
            "sku": sku_data["sku"].upper(),
            "sku2": sku_data.get("sku2", ""),
            "name": sku_data["name"],
            "url": sku_data.get("url", ""),
            "platform": sku_data.get("platform", ""),
            "roleid": sku_data.get("role_id", ""),
            "role": sku_data.get("role", ""),
        }
        self.bot.set_sku_data(self.sku_data)
        self.save_skutto_products_cache()

    def reject_pending_sku(self, sku_id: int):
        self.db.reject_sku(sku_id, 0)

    def get_emails(self, search: str = "") -> list[dict[str, Any]]:
        rows = self.db.get_all_emails()
        search = search.lower().strip()
        if search:
            rows = [row for row in rows if search in row["email"].lower() or search in str(row["discord_id"])]
        return rows

    def upsert_email(self, form):
        old_email = form.get("old_email", "").strip().lower()
        old_discord_id = self._int_or_none(form.get("old_discord_id", ""))
        email = form.get("email", "").strip().lower()
        discord_id = self._int_or_none(form.get("discord_id", ""))
        if not email or discord_id is None:
            raise ValueError("Email and Discord ID are required")
        if old_email and old_discord_id is not None:
            self.db.remove_email(old_email, old_discord_id)
        if not self.db.add_email(email, discord_id):
            if old_email and old_discord_id is not None:
                self.db.add_email(old_email, old_discord_id)
            raise ValueError("Email already exists")
        self.bot.refresh_data()

    def delete_email(self, email: str, discord_id: int):
        self.db.remove_email(email, discord_id)
        self.bot.refresh_data()

    def bulk_import_emails(self, raw_mappings: str) -> dict[str, Any]:
        text = str(raw_mappings or "").strip()
        if not text:
            raise ValueError("No email mappings were provided")

        added = 0
        skipped = 0
        errors = []
        reader = csv.reader(StringIO(text))
        for line_number, row in enumerate(reader, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue

            cells = [cell.strip() for cell in row]
            if line_number == 1 and cells[0].lower() in {"email", "emails"}:
                continue

            if len(cells) < 2:
                errors.append(f"Line {line_number}: expected email,discord_id")
                continue

            email = cells[0].lower()
            discord_raw = cells[1]
            if not email:
                errors.append(f"Line {line_number}: email is missing")
                continue
            try:
                discord_id = int(discord_raw)
            except ValueError:
                errors.append(f"Line {line_number}: Discord ID must be numeric")
                continue

            if self.db.add_email(email, discord_id):
                added += 1
            else:
                skipped += 1

        self.bot.refresh_data()
        self.add_log(f"Bulk email import complete: {added} added, {skipped} skipped, {len(errors)} errors")
        return {"added": added, "skipped": skipped, "errors": errors}

    def get_platforms(self) -> list[dict[str, Any]]:
        return self.db.get_all_platform_sites()

    def upsert_platform(self, form):
        platform_id = form.get("platform_id", "").strip()
        platform = form.get("platform", "").strip()
        site_url = form.get("site_url", "").strip()
        if not platform or not site_url:
            raise ValueError("Platform and site URL are required")
        if platform_id:
            self.db.update_platform_site(int(platform_id), platform, site_url)
        else:
            self.db.add_platform_site(platform, site_url)

    def delete_platform(self, platform_id: int):
        self.db.delete_platform_site(platform_id)

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
