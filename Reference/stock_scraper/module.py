"""
Stock Scraper Module

Main module class for the Stock Scraper.
"""

import time
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from frontlines.core.base_module import BaseModule
from frontlines.modules.stock_scraper.config import StockScraperConfig
from frontlines.modules.stock_scraper.tracker import ProductTracker
from frontlines.modules.stock_scraper.singles_detector import SinglesDetector


class StockScraperModule(BaseModule):
    """Stock Scraper module for monitoring Shopify stores.

    Monitors configured Shopify stores for products matching keywords
    and sends Discord notifications when new/updated products are found.
    """

    MODULE_ID = "stock_scraper"
    MODULE_NAME = "Stock Scraper"
    MODULE_VERSION = "2.0.0"
    MODULE_DESCRIPTION = "Monitors Shopify stores for keyword matches"

    def __init__(self, services):
        """Initialize the Stock Scraper module."""
        super().__init__(services)

        # Initialize tracker
        self.tracker = ProductTracker(self.data_path / "found.json")

        # Data
        self.stores: List[str] = []
        self.keywords: List[str] = []

        # Load stores and keywords
        self._load_stores()
        self._load_keywords()

    def _load_config(self) -> None:
        """Load module configuration."""
        self.config = StockScraperConfig.load(self.config_path)

    def _load_stores(self) -> None:
        """Load stores from file."""
        self.stores.clear()
        stores_file = self.data_path / "stores.txt"

        if not stores_file.exists():
            # Create template file
            with open(stores_file, 'w') as f:
                f.write("# Store URLs - one per line\n")
                f.write("# Example: example.myshopify.com\n")
            return

        try:
            with open(stores_file, 'r', encoding='utf-8') as f:
                for line in f:
                    store = line.strip()
                    if store and not store.startswith('#'):
                        self.stores.append(store)
        except Exception as e:
            self.log(f"Error loading stores: {e}", "error")

    def _load_keywords(self) -> None:
        """Load keywords from file."""
        self.keywords.clear()
        keywords_file = self.data_path / "keywords.txt"

        if not keywords_file.exists():
            # Create template file
            with open(keywords_file, 'w') as f:
                f.write("# Keywords - one per line (case insensitive)\n")
                f.write("# Example: booster box\n")
            return

        try:
            with open(keywords_file, 'r', encoding='utf-8') as f:
                for line in f:
                    keyword = line.strip().lower()
                    if keyword and not keyword.startswith('#'):
                        self.keywords.append(keyword)
        except Exception as e:
            self.log(f"Error loading keywords: {e}", "error")

    def reload_data(self) -> None:
        """Reload stores and keywords from files."""
        self._load_stores()
        self._load_keywords()
        self.log(f"Reloaded: {len(self.stores)} stores, {len(self.keywords)} keywords")

    def create_ui(self, parent):
        """Create the module's UI frame."""
        from frontlines.modules.stock_scraper.ui import StockScraperUI
        return StockScraperUI(parent, self)

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        # Validate we have stores and keywords
        if not self.stores:
            self.log("No stores configured - check stores.txt", "warning")

        if not self.keywords:
            self.log("No keywords configured - check keywords.txt", "warning")

        # Check webhook status
        if not self.config.main_webhook and not self.config.singles_webhook:
            self.log("Running in DATA COLLECTION MODE (no webhooks)", "warning")

        self.log(f"Using {self.config.max_workers} concurrent workers")

        while not self._stop_flag.is_set():
            self.log("Starting check cycle...")
            cycle_start = time.time()

            # Check stores concurrently
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                future_to_store = {
                    executor.submit(self._check_store, store): store
                    for store in self.stores
                }

                for future in as_completed(future_to_store):
                    if self._stop_flag.is_set():
                        break

                    store = future_to_store[future]
                    try:
                        future.result()
                    except Exception as e:
                        self.log(f"Error checking {store}: {e}", "error")

            cycle_duration = time.time() - cycle_start
            self.log(f"Cycle completed in {cycle_duration:.1f}s", "success")

            # Save tracker
            self.tracker.save()

            # Wait for next cycle
            self.log(f"Waiting {self.config.check_interval}s...")
            for _ in range(self.config.check_interval):
                if self._stop_flag.is_set():
                    break
                time.sleep(1)

    def _check_store(self, store: str) -> None:
        """Check a single store for matching products."""
        if self.config.detailed_logging:
            self.log(f"Checking: {store}")

        products_found = 0
        pages_checked = 0

        for page in range(1, self.config.max_pages + 1):
            if self._stop_flag.is_set():
                break

            products = self.services.http.fetch_shopify_products(store, page)

            if products is None:
                if page == 1:
                    self.log(f"Failed to fetch {store}", "warning")
                break

            if not products:
                break

            pages_checked += 1
            products_found += len(products)

            for product in products:
                if self._stop_flag.is_set():
                    break
                self._process_product(store, product)

        if self.config.detailed_logging and pages_checked > 0:
            self.log(f"{store}: {products_found} products, {pages_checked} pages")

    def _process_product(self, store: str, product: Dict) -> None:
        """Process a single product."""
        # Check for keyword matches
        title_lower = product.get('title', '').lower()
        matched_keywords = [k for k in self.keywords if k in title_lower]

        if not matched_keywords:
            return

        # Detect if it's a single
        is_single = SinglesDetector.is_single(product)

        # Check variants
        product_id = str(product.get('id', ''))
        product_title = product.get('title', 'Unknown')
        variants = product.get('variants', [])

        should_notify = False
        for variant in variants:
            if not isinstance(variant, dict):
                continue

            variant_id = str(variant.get('id', ''))
            price = variant.get('price', '')
            available = variant.get('available', False)

            if self.tracker.update_variant(
                store, product_id, variant_id, price, available, product_title
            ):
                should_notify = True

        # Send notification
        if should_notify:
            self._send_notification(store, product, matched_keywords, is_single)

    def _send_notification(
        self,
        store: str,
        product: Dict,
        keywords: List[str],
        is_single: bool
    ) -> None:
        """Send Discord notification for a product."""
        # Check webhooks
        no_webhooks = not self.config.main_webhook and not self.config.singles_webhook

        if no_webhooks:
            if self.config.detailed_logging:
                ptype = "SINGLE" if is_single else "product"
                self.log(f"Tracked {ptype}: {product.get('title', '')[:40]}")
            return

        # Skip singles if ignored
        if is_single and self.config.ignore_singles:
            if self.config.detailed_logging:
                self.log(f"Skipped single: {product.get('title', '')[:40]}")
            return

        # Choose webhook
        if is_single and self.config.singles_webhook:
            webhook_url = self.config.singles_webhook
        elif self.config.main_webhook:
            webhook_url = self.config.main_webhook
        else:
            return

        # Build notification
        product_url = f"https://{store}/products/{product.get('handle', '')}"

        # Get thumbnail
        thumbnail_url = None
        if product.get('image') and isinstance(product['image'], dict):
            thumbnail_url = product['image'].get('src')
        elif product.get('images') and isinstance(product['images'], list):
            for img in product['images']:
                if isinstance(img, dict) and img.get('src'):
                    thumbnail_url = img['src']
                    break

        # Build variant info
        variants = product.get('variants', [])
        variant_lines = []
        for variant in variants[:3]:
            if not isinstance(variant, dict):
                continue
            title = variant.get('title', 'Default')
            price = variant.get('price', 'N/A')
            stock = 'In Stock' if variant.get('available') else 'Out of Stock'
            variant_lines.append(f"{title} - ${price} - {stock}")

        variants_text = '\n'.join(variant_lines)
        if len(variants) > 3:
            variants_text += f"\n...and {len(variants) - 3} more"

        # Get first variant for ATC
        first_var_id = str(variants[0]['id']) if variants else str(product.get('id', ''))
        atc_link = f"https://{store}/cart/{first_var_id}:1"

        # Build fields
        fields = [
            {"name": "Store", "value": store, "inline": True},
            {"name": "Keywords", "value": ", ".join(keywords), "inline": True},
            {"name": "Add to Cart", "value": f"[ATC Link]({atc_link})", "inline": True},
        ]

        if variants_text:
            fields.append({"name": "Variants", "value": variants_text, "inline": False})

        # Send embed
        description = ""
        if is_single:
            description = "**SINGLE DETECTED**\n\n"
        description += f"New/updated item from **{store}**"

        color = 0xFF6B6B if is_single else 0x4ECDC4

        success = self.services.discord.send_embed(
            webhook_url=webhook_url,
            title=product.get('title', 'Unknown Product'),
            description=description,
            color=color,
            fields=fields,
            thumbnail_url=thumbnail_url,
            url=product_url,
            footer_text="FrontLines - Stock Scraper"
        )

        if success:
            ptype = "SINGLE" if is_single else "product"
            self.log(f"Notified: {product.get('title', '')[:40]}", "success")
        else:
            self.log(f"Failed to send notification", "error")

    def get_status(self) -> Dict:
        """Get module status with additional info."""
        status = super().get_status()
        status.update({
            'stores': len(self.stores),
            'keywords': len(self.keywords),
            'tracked': self.tracker.get_stats(),
            'proxies': self.services.proxy.count,
        })
        return status
