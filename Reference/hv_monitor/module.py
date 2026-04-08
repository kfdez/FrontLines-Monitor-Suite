"""
HV Monitor Module

Monitors specific Shopify products via GraphQL API.
"""

import time
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

from frontlines.core.base_module import BaseModule
from frontlines.modules.hv_monitor.config import HVMonitorConfig


class HVMonitorModule(BaseModule):
    """HV Monitor module for tracking specific product IDs.

    Monitors a list of Shopify product/variant IDs and sends
    Discord notifications when items come back in stock.
    """

    MODULE_ID = "hv_monitor"
    MODULE_NAME = "HV Monitor"
    MODULE_VERSION = "2.0.0"
    MODULE_DESCRIPTION = "Monitors specific Shopify products via GraphQL"

    def __init__(self, services):
        """Initialize the HV Monitor module."""
        super().__init__(services)

        # Stock tracking
        self.stock_status: Dict[str, bool] = {}
        self.metadata: Dict[str, Dict[str, str]] = {}
        self.products: List[Tuple[str, bool]] = []  # (id, ping_override)

        # Load data
        self._load_stock_status()
        self._load_metadata()
        self._load_products()

    def _load_config(self) -> None:
        """Load module configuration."""
        self.config = HVMonitorConfig.load(self.config_path)

    def _load_stock_status(self) -> None:
        """Load stock status from file."""
        status_file = self.data_path / "stock_status.json"
        if status_file.exists():
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    self.stock_status = json.load(f)
            except Exception:
                self.stock_status = {}

    def _save_stock_status(self) -> None:
        """Save stock status to file."""
        status_file = self.data_path / "stock_status.json"
        try:
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(self.stock_status, f)
        except Exception as e:
            self.log(f"Error saving stock status: {e}", "error")

    def _load_metadata(self) -> None:
        """Load product metadata."""
        meta_file = self.data_path / "metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except Exception:
                self.metadata = {}

    def _save_metadata(self) -> None:
        """Save product metadata."""
        meta_file = self.data_path / "metadata.json"
        try:
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            self.log(f"Error saving metadata: {e}", "error")

    def _load_products(self) -> None:
        """Load products from file."""
        self.products.clear()
        products_file = self.data_path / "products.txt"

        if not products_file.exists():
            # Create template
            with open(products_file, 'w') as f:
                f.write("# Product/Variant IDs - one per line\n")
                f.write("# Add |ping after ID to enable role ping for that item\n")
                f.write("# Example: gid://shopify/ProductVariant/123456|ping\n")
            return

        try:
            with open(products_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    if '|ping' in line:
                        self.products.append((line.replace('|ping', ''), True))
                    else:
                        self.products.append((line, False))
        except Exception as e:
            self.log(f"Error loading products: {e}", "error")

    def _save_products(self) -> None:
        """Save products to file."""
        products_file = self.data_path / "products.txt"
        try:
            with open(products_file, 'w', encoding='utf-8') as f:
                for product_id, ping in self.products:
                    if ping:
                        f.write(f"{product_id}|ping\n")
                    else:
                        f.write(f"{product_id}\n")
        except Exception as e:
            self.log(f"Error saving products: {e}", "error")

    def reload_data(self) -> None:
        """Reload products from file."""
        self._load_products()
        self._load_metadata()
        self.log(f"Reloaded: {len(self.products)} products")

    def add_product(self, product_id: str, ping: bool = False, meta: Dict = None) -> bool:
        """Add a product to monitor.

        Args:
            product_id: Shopify product/variant GID
            ping: Whether to ping role for this item
            meta: Optional metadata (title, price, etc.)

        Returns:
            True if added, False if already exists
        """
        # Check if exists
        for existing_id, _ in self.products:
            if existing_id == product_id:
                return False

        self.products.append((product_id, ping))
        self._save_products()

        if meta:
            self.metadata[product_id] = meta
            self._save_metadata()

        return True

    def remove_product(self, product_id: str) -> bool:
        """Remove a product from monitoring.

        Args:
            product_id: Product ID to remove

        Returns:
            True if removed
        """
        original_len = len(self.products)
        self.products = [(pid, ping) for pid, ping in self.products if pid != product_id]

        if len(self.products) < original_len:
            self._save_products()

            if product_id in self.metadata:
                del self.metadata[product_id]
                self._save_metadata()

            return True
        return False

    def create_ui(self, parent):
        """Create the module's UI frame."""
        from frontlines.modules.hv_monitor.ui import HVMonitorUI
        return HVMonitorUI(parent, self)

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        if not self.products:
            self.log("No products configured", "warning")

        if not self.config.token:
            self.log("No API token configured", "warning")

        while not self._stop_flag.is_set():
            current_status = {}

            for product_id, ping_override in self.products:
                if self._stop_flag.is_set():
                    break

                try:
                    # Get product name from metadata
                    meta = self.metadata.get(product_id, {})
                    name = meta.get('title', product_id[:30])

                    self.log(f"Checking: {name}")
                    self._check_product(product_id, ping_override, current_status)

                except Exception as e:
                    self.log(f"Error checking {product_id}: {e}", "error")

            # Update stock status
            self.stock_status = current_status
            self._save_stock_status()

            # Wait for next cycle
            for _ in range(self.config.check_interval):
                if self._stop_flag.is_set():
                    break
                time.sleep(1)

    def _check_product(
        self,
        product_id: str,
        ping_override: bool,
        current_status: Dict[str, bool]
    ) -> None:
        """Check a single product's stock status."""
        query = self._build_query(product_id)

        data = self.services.http.graphql_request(
            self.config.store_url,
            query,
            self.config.token
        )

        if not data:
            self.log(f"No response for {product_id}", "warning")
            return

        node = data.get("data", {}).get("node")
        if not node:
            return

        # Handle product with variants
        if node.get("variants"):
            product = node
            for v in product["variants"]["edges"]:
                variant = v["node"]
                var_id = variant["id"]
                available = variant["availableForSale"]

                current_status[var_id] = available

                # Check if back in stock
                if available and not self.stock_status.get(var_id, False):
                    self.log(f"Back in stock: {product['title']} - {variant['title']}", "success")
                    self._send_notification(product, variant, ping_override)

        # Handle single variant
        elif node.get("product"):
            product = node["product"]
            variant = node
            var_id = variant["id"]
            available = variant["availableForSale"]

            current_status[var_id] = available

            if available and not self.stock_status.get(var_id, False):
                self.log(f"Back in stock: {product['title']} - {variant['title']}", "success")
                self._send_notification(product, variant, ping_override)

    def _build_query(self, product_id: str) -> str:
        """Build GraphQL query for product."""
        return f"""
        {{
          node(id: "{product_id}") {{
            ... on Product {{
              id
              title
              availableForSale
              onlineStoreUrl
              images(first: 1) {{ edges {{ node {{ src }} }} }}
              variants(first: 10) {{
                edges {{
                  node {{
                    id
                    title
                    availableForSale
                    price {{ amount currencyCode }}
                  }}
                }}
              }}
            }}
            ... on ProductVariant {{
              id
              title
              availableForSale
              price {{ amount currencyCode }}
              product {{
                id
                title
                onlineStoreUrl
                images(first: 1) {{ edges {{ node {{ src }} }} }}
              }}
            }}
          }}
        }}
        """

    def _send_notification(
        self,
        product: Dict,
        variant: Optional[Dict],
        ping_override: bool
    ) -> None:
        """Send Discord notification for back-in-stock item."""
        if not self.config.discord_webhook:
            return

        # Get thumbnail
        thumbnail_url = None
        try:
            if variant and "product" in variant and "images" in variant["product"]:
                imgs = variant["product"]["images"]["edges"]
                if imgs:
                    thumbnail_url = imgs[0]["node"]["src"]
            elif "images" in product and "edges" in product["images"]:
                imgs = product["images"]["edges"]
                if imgs:
                    thumbnail_url = imgs[0]["node"]["src"]
        except Exception:
            pass

        # Build fields
        fields = []
        if variant:
            fields.extend([
                {"name": "Variant", "value": variant["title"], "inline": True},
                {"name": "Price", "value": f"{variant['price']['amount']} {variant['price']['currencyCode']}", "inline": True},
                {"name": "Variant ID", "value": f"`{variant['id']}`", "inline": False}
            ])
        else:
            fields.append({"name": "Product ID", "value": f"`{product['id']}`", "inline": False})

        # Determine if should ping
        mention_role = None
        if ping_override or self.config.ping_role:
            mention_role = self.config.discord_role_id

        # Send
        self.services.discord.send_embed(
            webhook_url=self.config.discord_webhook,
            title=product["title"],
            url=product.get("onlineStoreUrl", ""),
            color=0x00ff00,
            fields=fields,
            thumbnail_url=thumbnail_url,
            mention_role=mention_role,
            footer_text="FrontLines - HV Monitor"
        )

    def search_products(self, keyword: str) -> List[Dict]:
        """Search for products by keyword.

        Args:
            keyword: Search keyword

        Returns:
            List of product results
        """
        query = f"""
        {{
          products(first: {self.config.search_limit}, query: "{keyword}") {{
            edges {{
              node {{
                id
                title
                availableForSale
                onlineStoreUrl
                images(first: 1) {{
                    edges {{ node {{ src }} }}
                }}
                variants(first: 10) {{
                  edges {{
                    node {{
                      id
                      title
                      availableForSale
                      price {{ amount currencyCode }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """

        data = self.services.http.graphql_request(
            self.config.store_url,
            query,
            self.config.token
        )

        if not data:
            return []

        products = data.get("data", {}).get("products", {}).get("edges", [])
        return [edge["node"] for edge in products]

    def get_status(self) -> Dict:
        """Get module status with additional info."""
        status = super().get_status()
        status.update({
            'products': len(self.products),
            'tracked_variants': len(self.stock_status),
        })
        return status
