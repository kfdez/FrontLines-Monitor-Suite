"""
HV Monitor Backend

Monitors specific Shopify products via GraphQL API and sends Discord webhooks
when items come back in stock.
"""

import json
import os
import sys
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus
import requests


def encode_proxy(proxy: str) -> str:
    """Encode proxy URL for requests with special characters in password."""
    if not proxy or ':' not in proxy:
        return proxy
    parts = proxy.split(':')
    if len(parts) >= 4:
        # Format: host:port:username:password -> http://username:password@host:port
        host = parts[0]
        port = parts[1]
        username = parts[2]
        password = ':'.join(parts[3:])  # Handle password with colons
        return f"http://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}"
    return f"http://{proxy}"


class HVMonitor:
    """HV Monitor for tracking specific Shopify product/variant IDs."""

    def __init__(self, db, log_callback=None, app=None, data_dir: str = None):
        """Initialize the HV Monitor.

        Args:
            db: Database instance for config storage
            log_callback: Optional callback function for logging messages
            app: Optional app reference for accessing proxies
        """
        self.db = db
        self.log_callback = log_callback
        self.app = app

        # Additional log callback for HV monitor's own log panel
        self.hv_log_callback = None

        # UI callback for refreshing product list
        self.ui_refresh_callback = None

        # Configuration (loaded from database)
        self.store_url = ""
        self.token = ""
        self.webhook_url = ""
        self.role_id = ""
        self.ping_enabled = False
        self.check_interval = 30
        self.auto_start = False

        # Products to monitor: List of (product_id, ping_enabled)
        self.products: List[Tuple[str, bool]] = []

        # Data directory - use exe directory if bundled
        if data_dir:
            self.data_dir = data_dir
        elif getattr(sys, 'frozen', False):
            self.data_dir = os.path.join(os.path.dirname(sys.executable), "hv_monitor_data")
        else:
            self.data_dir = "hv_monitor_data"

        # Product metadata: product_id -> metadata dict
        self.metadata: Dict[str, Dict] = {}

        # Stock status: product_id -> available (bool)
        self.stock_status: Dict[str, bool] = {}

        # Monitoring state
        self._stop_flag = threading.Event()
        self._monitor_thread = None
        self._running = False

        # Proxy management
        self._proxies: List[str] = []
        self._proxy_index = 0
        self._failed_proxies: set = set()

        # Data file paths
        self._ensure_data_dir()

        # Load configuration and data
        self.load_config()
        self.load_products()
        self.load_metadata()
        self.load_stock_status()

    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def log(self, message: str):
        """Log a message via callbacks."""
        if self.log_callback:
            self.log_callback(message)
        if self.hv_log_callback:
            self.hv_log_callback(message)
        print(f"[HVMonitor] {message}")

    def _load_proxies(self):
        """Load proxies from app if available."""
        self._proxies = []
        self._failed_proxies = set()
        self._proxy_index = 0
        if self.app and hasattr(self.app, 'proxies'):
            self._proxies = list(self.app.proxies)
        if self._proxies:
            self.log(f"Loaded {len(self._proxies)} proxies")

    def _get_proxy(self) -> Optional[str]:
        """Get next available proxy, rotating on failure."""
        if not self._proxies:
            return None

        # Filter out failed proxies
        available = [p for p in self._proxies if p not in self._failed_proxies]
        if not available:
            # Reset failed proxies if all have failed
            self._failed_proxies.clear()
            available = self._proxies

        # Rotate through proxies and encode special characters
        proxy = available[self._proxy_index % len(available)]
        self._proxy_index += 1
        return encode_proxy(proxy)

    def _on_proxy_failure(self, proxy: str):
        """Mark a proxy as failed and rotate to next."""
        if proxy:
            self._failed_proxies.add(proxy)
            self.log(f"Proxy failed: {proxy}")

    # ============ CONFIG OPERATIONS ============

    def load_config(self):
        """Load configuration from database."""
        self.store_url = self.db.get_config("hv_store_url", "")
        self.token = self.db.get_config("hv_token", "")
        self.webhook_url = self.db.get_config("hv_webhook", "")
        self.role_id = self.db.get_config("hv_role_id", "")
        self.ping_enabled = self.db.get_config("hv_ping_enabled", "false").lower() == "true"
        self.check_interval = int(self.db.get_config("hv_check_interval", "30"))
        self.auto_start = self.db.get_config("hv_auto_start", "false").lower() == "true"

    def save_config(self):
        """Save configuration to database."""
        self.db.set_config("hv_store_url", self.store_url)
        self.db.set_config("hv_token", self.token)
        self.db.set_config("hv_webhook", self.webhook_url)
        self.db.set_config("hv_role_id", self.role_id)
        self.db.set_config("hv_ping_enabled", "true" if self.ping_enabled else "false")
        self.db.set_config("hv_check_interval", str(self.check_interval))
        self.db.set_config("hv_auto_start", "true" if self.auto_start else "false")

    # ============ PRODUCT OPERATIONS ============

    def load_products(self):
        """Load monitored products from file."""
        self.products = []
        products_file = os.path.join(self.data_dir, "products.txt")

        if not os.path.exists(products_file):
            # Create template file
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
            self.log(f"Error loading products: {e}")

    def save_products(self):
        """Save monitored products to file."""
        products_file = os.path.join(self.data_dir, "products.txt")
        try:
            with open(products_file, 'w', encoding='utf-8') as f:
                for product_id, ping in self.products:
                    if ping:
                        f.write(f"{product_id}|ping\n")
                    else:
                        f.write(f"{product_id}\n")
        except Exception as e:
            self.log(f"Error saving products: {e}")

    def load_metadata(self):
        """Load product metadata from file."""
        meta_file = os.path.join(self.data_dir, "metadata.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            except Exception:
                self.metadata = {}

    def save_metadata(self):
        """Save product metadata to file."""
        meta_file = os.path.join(self.data_dir, "metadata.json")
        try:
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            self.log(f"Error saving metadata: {e}")

    def load_stock_status(self):
        """Load stock status from file."""
        status_file = os.path.join(self.data_dir, "stock_status.json")
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    self.stock_status = json.load(f)
            except Exception:
                self.stock_status = {}

    def save_stock_status(self):
        """Save stock status to file."""
        status_file = os.path.join(self.data_dir, "stock_status.json")
        try:
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(self.stock_status, f)
        except Exception as e:
            self.log(f"Error saving stock status: {e}")

    # ============ PRODUCT MANAGEMENT ============

    def add_product(self, product_id: str, ping: bool = False, meta: Dict = None) -> bool:
        """Add a product to monitor.

        Args:
            product_id: Shopify product/variant GID
            ping: Whether to ping role for this item
            meta: Optional metadata (title, price, etc.)

        Returns:
            True if added, False if already exists
        """
        # Check if already exists
        for existing_id, _ in self.products:
            if existing_id == product_id:
                return False

        self.products.append((product_id, ping))
        self.save_products()

        if meta:
            self.metadata[product_id] = meta
            self.save_metadata()

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
            self.save_products()

            if product_id in self.metadata:
                del self.metadata[product_id]
                self.save_metadata()

            return True
        return False

    def toggle_product_ping(self, product_id: str) -> bool:
        """Toggle ping setting for a product.

        Args:
            product_id: Product ID to toggle

        Returns:
            New ping state, or None if not found
        """
        for i, (pid, ping) in enumerate(self.products):
            if pid == product_id:
                self.products[i] = (pid, not ping)
                self.save_products()
                return not ping
        return None

    def reset_stock_status(self, product_id: str):
        """Reset stock status for a product to trigger alert on next check.

        Args:
            product_id: Product ID to reset
        """
        # Clear all stock status - since we can't easily map products to their variants
        # This ensures the product will trigger an alert on next check
        self.stock_status.clear()
        self.log(f"Stock status reset for all products")

    def reload_data(self):
        """Reload products and metadata from files."""
        self.load_products()
        self.load_metadata()
        self.log(f"Reloaded: {len(self.products)} products")

    # ============ GRAPHQL API ============

    def _graphql_request(self, query: str, retries: int = 3, timeout: int = 30) -> Optional[Dict]:
        """Make a GraphQL request to Shopify.

        Args:
            query: GraphQL query string
            retries: Number of retries on failure
            timeout: Request timeout in seconds

        Returns:
            Response JSON dict, or None on error
        """
        if not self.store_url or not self.token:
            self.log("Store URL or token not configured")
            return None

        for attempt in range(retries):
            proxy = self._get_proxy()

            try:
                response = requests.post(
                    self.store_url,
                    json={"query": query},
                    headers={
                        "Content-Type": "application/json",
                        "X-Shopify-Storefront-Access-Token": self.token
                    },
                    proxies={"http": proxy, "https": proxy} if proxy else None,
                    timeout=timeout
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                self.log(f"GraphQL request failed (attempt {attempt + 1}/{retries}): {e}")
                if proxy:
                    self._on_proxy_failure(proxy)

        return None

    def search_products(self, keyword: str, limit: int = 10) -> List[Dict]:
        """Search for products by keyword.

        Args:
            keyword: Search keyword
            limit: Maximum results

        Returns:
            List of product dicts
        """
        keyword = keyword.strip()
        if not keyword:
            return []

        query_text = json.dumps(keyword)
        query = f"""
        {{
          products(first: {limit}, query: {query_text}) {{
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

        data = self._graphql_request(query, retries=1, timeout=12)
        if not data:
            return []

        products = data.get("data", {}).get("products", {}).get("edges", [])
        return [edge["node"] for edge in products]

    def _build_product_query(self, product_id: str) -> str:
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

    # ============ MONITORING ============

    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running

    def start(self):
        """Start the monitoring thread."""
        if self._running:
            return

        if not self.products:
            self.log("No products configured")

        if not self.token:
            self.log("API token not configured")

        self._stop_flag.clear()
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self.log("Monitor started")

    def stop(self):
        """Stop the monitoring thread."""
        if not self._running:
            return

        self._stop_flag.set()
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.log("Monitor stopped")

    def _monitor_loop(self):
        """Main monitoring loop."""
        # Load proxies at startup
        self._load_proxies()

        if self._proxies:
            self.log(f"Using {len(self._proxies)} proxies")
        else:
            self.log("No proxies configured")

        while not self._stop_flag.is_set():
            current_status = {}

            for product_id, ping_override in self.products:
                if self._stop_flag.is_set():
                    break

                try:
                    meta = self.metadata.get(product_id, {})
                    name = meta.get('title', product_id[:30])

                    self.log(f"Checking: {name}")
                    self._check_product(product_id, ping_override, current_status)

                except Exception as e:
                    self.log(f"Error checking {product_id}: {e}")

            # Update stock status
            self.stock_status = current_status
            self.save_stock_status()

            # Wait for next cycle
            for _ in range(self.check_interval):
                if self._stop_flag.is_set():
                    break
                time.sleep(1)

    def _check_product(
        self,
        product_id: str,
        ping_override: bool,
        current_status: Dict[str, bool]
    ):
        """Check a single product's stock status."""
        query = self._build_product_query(product_id)
        data = self._graphql_request(query)

        if not data:
            self.log(f"No response for {product_id}")
            return

        node = data.get("data", {}).get("node")
        if not node:
            return

        # Update metadata if missing
        if product_id not in self.metadata or not self.metadata[product_id].get('title'):
            if node.get("variants"):
                # It's a Product
                self.metadata[product_id] = {"title": node["title"], "type": "product"}
            elif node.get("product"):
                # It's a Variant
                product = node["product"]
                self.metadata[product_id] = {
                    "title": f"{product['title']} - {node['title']}",
                    "price": f"{node['price']['amount']} {node['price']['currencyCode']}",
                    "type": "variant"
                }
            else:
                self.metadata[product_id] = {"title": product_id[:30], "type": "unknown"}
            self.save_metadata()
            # Notify UI to refresh if callback is set
            if self.ui_refresh_callback:
                self.ui_refresh_callback()

        # Handle product with variants
        if node.get("variants"):
            product = node
            for v in product["variants"]["edges"]:
                variant = v["node"]
                var_id = variant["id"]
                available = variant["availableForSale"]

                current_status[var_id] = available

                # Check if back in stock (or first time seeing it in stock)
                prev_status = self.stock_status.get(var_id)
                if available and prev_status is not True:
                    self.log(f"Back in stock: {product['title']} - {variant['title']}")
                    self._send_notification(product, variant, ping_override)

        # Handle single variant
        elif node.get("product"):
            product = node["product"]
            variant = node
            var_id = variant["id"]
            available = variant["availableForSale"]

            current_status[var_id] = available

            # Check if back in stock (or first time seeing it in stock)
            prev_status = self.stock_status.get(var_id)
            if available and prev_status is not True:
                self.log(f"Back in stock: {product['title']} - {variant['title']}")
                self._send_notification(product, variant, ping_override)

    # ============ DISCORD NOTIFICATIONS ============

    def _send_notification(
        self,
        product: Dict,
        variant: Optional[Dict],
        ping_override: bool
    ):
        """Send Discord notification for back-in-stock item."""
        if not self.webhook_url:
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

        # Check if product has a URL (if not, it's APP-ONLY)
        product_url = product.get("onlineStoreUrl", "")
        is_app_only = not product_url

        # Build embed
        embed = {
            "title": product["title"],
            "url": product_url if product_url else None,
            "color": 0x00FF00,  # Green
            "footer": {"text": f"FrontLines - Hobbiesville Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"},
            "fields": []
        }

        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}

        if variant:
            price = f"{variant['price']['amount']} {variant['price']['currencyCode']}"

            embed["fields"] = [
                {"name": "Variant", "value": variant["title"], "inline": True},
                {"name": "Price", "value": price, "inline": True},
            ]

            if is_app_only:
                embed["fields"].append({"name": "Type", "value": "APP-ONLY", "inline": False})
        else:
            embed["fields"] = [
                {"name": "Product ID", "value": f"`{product['id']}`", "inline": False}
            ]

        # Global ping is an allow switch; product-level ping decides whether this item mentions the role.
        content = ""
        if self.ping_enabled and ping_override:
            content = f"<@&{self.role_id}>" if self.role_id else ""

        # Send webhook
        try:
            payload = {"embeds": [embed]}
            if content:
                payload["content"] = content

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            self.log(f"Notification sent for {product['title']}")
        except requests.RequestException as e:
            self.log(f"Failed to send notification: {e}")

    # ============ STATUS ============

    def get_status(self) -> Dict:
        """Get monitor status."""
        return {
            "running": self._running,
            "products": len(self.products),
            "tracked_variants": len(self.stock_status),
            "store_url": self.store_url,
            "ping_enabled": self.ping_enabled,
            "check_interval": self.check_interval
        }
