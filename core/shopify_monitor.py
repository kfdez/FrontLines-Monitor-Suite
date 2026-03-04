"""
Shopify Monitor Backend

Monitors Shopify stores for products matching keywords
and sends Discord notifications when new/updated products are found.
"""

import json
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Any
import requests


class ProductFilter:
    """Filters out unwanted products like card singles and graded slabs."""

    # Card number patterns - matches things like "123/456", "001 ME", "H1"
    CARD_NUMBER_PATTERNS = [
        re.compile(r'\b\d{1,3}/\d{1,3}\b'),  # 123/456
        re.compile(r'\b\d{3}\s+[A-Z]{1,3}\b'),  # 001 ME
        re.compile(r'\b[A-Z]\d{1,2}\b'),  # H1, A12
        re.compile(r'\b\d{1,3}\s*[Pp][Ff]\b'),  # 001 PF
        re.compile(r'\b[A-Z]{1,2}\s*\d{1,3}\b'),  # AM 123
    ]

    # Graded slab keywords
    GRADED_KEYWORDS = [
        "PSA", "BGS", "CGC", "NGC", "PCGS",
        "GEM MINT", "PRISTINE", "MINT", "NM-MT",
        "GEM MT", "GEMMT", "MT", "GEM MINT 10",
        "BGS 10", "BGS 9.5", "PSA 10", "PSA 9.5",
        "CGC 10", "CGC 9.5", "SLAB", "GRADED",
    ]

    # Condition keywords that indicate singles
    CONDITION_PATTERNS = [
        re.compile(r'\bNear\s*Mint\b', re.IGNORECASE),
        re.compile(r'\bLightly\s*Played\b', re.IGNORECASE),
        re.compile(r'\bModerately\s*Played\b', re.IGNORECASE),
        re.compile(r'\bHeavily\s*Played\b', re.IGNORECASE),
        re.compile(r'\bDamaged\b', re.IGNORECASE),
        re.compile(r'\bNM\b'),
        re.compile(r'\bLP\b'),
        re.compile(r'\bMP\b'),
        re.compile(r'\bHP\b'),
        re.compile(r'\bDMG\b'),
    ]

    @classmethod
    def is_card_single(cls, product: Dict) -> bool:
        """Determine if a product is a card single based on title patterns."""
        title = product.get('title', '')

        # Check title for card number patterns
        for pattern in cls.CARD_NUMBER_PATTERNS:
            if pattern.search(title):
                return True

        # Check variants for condition patterns
        variants = product.get('variants', [])
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            variant_title = variant.get('title', '')
            for pattern in cls.CONDITION_PATTERNS:
                if pattern.search(variant_title):
                    return True

        return False

    @classmethod
    def is_graded_slab(cls, product: Dict) -> bool:
        """Determine if a product is a graded slab."""
        title = product.get('title', '').upper()

        # Check for graded keywords
        for keyword in cls.GRADED_KEYWORDS:
            if keyword.upper() in title:
                return True

        return False

    @classmethod
    def should_monitor(cls, product: Dict) -> bool:
        """Determine if a product should be monitored (True = NOT filtered out)."""
        # Filter out card singles
        if cls.is_card_single(product):
            return False

        # Filter out graded slabs
        if cls.is_graded_slab(product):
            return False

        return True


class ProductTracker:
    """Tracks seen products to avoid duplicate notifications."""

    def __init__(self, tracker_file: str):
        """Initialize tracker."""
        self.tracker_file = tracker_file
        self.data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.lock = threading.Lock()
        self.load()

    def load(self) -> None:
        """Load tracked products from file."""
        if not os.path.exists(self.tracker_file):
            return
        try:
            with open(self.tracker_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except Exception:
            self.data = {}

    def save(self) -> None:
        """Save tracked products to file."""
        with self.lock:
            try:
                os.makedirs(os.path.dirname(self.tracker_file), exist_ok=True)
                with open(self.tracker_file, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                print(f"[ShopifyMonitor] Error saving tracker: {e}")

    def update_variant(
        self,
        store: str,
        prod_id: str,
        var_id: str,
        price: str,
        available: bool,
        product_title: str = None
    ) -> bool:
        """Check if we should send a notification for this variant."""
        with self.lock:
            if store not in self.data:
                self.data[store] = {}
            if prod_id not in self.data[store]:
                self.data[store][prod_id] = {}

            prev_state = self.data[store][prod_id].get(var_id, {})

            self.data[store][prod_id][var_id] = {
                'price': price,
                'available': available,
                'last_seen': datetime.now().isoformat()
            }

            if product_title and '_product_title' not in self.data[store][prod_id]:
                self.data[store][prod_id]['_product_title'] = product_title

            # Notify if: never seen, back in stock, or price changed while available
            if not prev_state:
                return True
            if not prev_state.get('available') and available:
                return True
            if available and prev_state.get('price') != price:
                return True

            return False

    def get_stats(self) -> Dict:
        """Get tracking statistics."""
        total_stores = len(self.data)
        total_products = sum(len(products) for products in self.data.values())
        total_variants = 0
        for products in self.data.values():
            for variants in products.values():
                total_variants += len([k for k in variants.keys() if not k.startswith('_')])

        return {
            'stores': total_stores,
            'products': total_products,
            'variants': total_variants,
        }

    def clear(self) -> None:
        """Clear all tracked data."""
        with self.lock:
            self.data.clear()


class ShopifyMonitor:
    """Shopify Monitor for tracking keyword-matched products from multiple stores."""

    def __init__(self, db, log_callback=None, app=None):
        """Initialize the Shopify Monitor."""
        self.db = db
        self.log_callback = log_callback
        self.app = app

        # Additional log callback for Shopify monitor's own log panel
        self.shopify_log_callback = None

        # UI callback for refreshing
        self.ui_refresh_callback = None

        # Configuration (loaded from database)
        self.main_webhook = ""
        self.singles_webhook = ""
        self.ignore_singles = False
        self.ping_role_id = ""
        self.ping_enabled = True
        self.max_pages = 3
        self.check_interval = 300
        self.request_timeout = 15
        self.max_workers = 3
        self.max_retries = 3
        self.webhook_delay = 0.8
        self.detailed_logging = False
        self.auto_start = False
        self.data_collection_mode = False

        # Products to monitor
        self.stores: List[str] = []
        self.keywords: List[str] = []

        # Proxy management
        self._proxies: List[str] = []
        self._proxy_index = 0
        self._failed_proxies: set = set()

        # Tracker
        self.tracker: Optional[ProductTracker] = None

        # Monitoring state
        self._stop_flag = threading.Event()
        self._monitor_thread = None
        self._running = False

        # Data file paths
        self.data_dir = "shopify_monitor_data"
        self._ensure_data_dir()

        # Load configuration (includes stores/keywords from database)
        self.load_config()
        self._init_tracker()

    def _ensure_data_dir(self):
        """Ensure data directory exists."""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def log(self, message: str):
        """Log a message via callbacks."""
        if self.log_callback:
            self.log_callback(message)
        if self.shopify_log_callback:
            self.shopify_log_callback(message)

    def load_config(self):
        """Load configuration from database."""
        self.main_webhook = self.db.get_config("shopify_main_webhook", "")
        self.singles_webhook = self.db.get_config("shopify_singles_webhook", "")
        self.ignore_singles = self.db.get_config("shopify_ignore_singles", "false").lower() == "true"
        self.ping_role_id = self.db.get_config("shopify_ping_role_id", "")
        self.ping_enabled = self.db.get_config("shopify_ping_enabled", "true").lower() == "true"
        self.max_pages = int(self.db.get_config("shopify_max_pages", "3"))
        self.check_interval = int(self.db.get_config("shopify_check_interval", "300"))
        self.request_timeout = int(self.db.get_config("shopify_request_timeout", "15"))
        self.max_workers = int(self.db.get_config("shopify_max_workers", "3"))
        self.max_retries = int(self.db.get_config("shopify_max_retries", "3"))
        self.webhook_delay = float(self.db.get_config("shopify_webhook_delay", "0.8"))
        self.detailed_logging = self.db.get_config("shopify_detailed_logging", "false").lower() == "true"
        self.auto_start = self.db.get_config("shopify_auto_start", "false").lower() == "true"
        self.data_collection_mode = self.db.get_config("shopify_data_collection_mode", "false").lower() == "true"

        # Load stores and keywords from database (JSON format)
        self._load_stores_keywords()

    def save_config(self):
        """Save configuration to database."""
        self.db.set_config("shopify_main_webhook", self.main_webhook)
        self.db.set_config("shopify_singles_webhook", self.singles_webhook)
        self.db.set_config("shopify_ignore_singles", "true" if self.ignore_singles else "false")
        self.db.set_config("shopify_ping_role_id", self.ping_role_id)
        self.db.set_config("shopify_ping_enabled", "true" if self.ping_enabled else "false")
        self.db.set_config("shopify_max_pages", str(self.max_pages))
        self.db.set_config("shopify_check_interval", str(self.check_interval))
        self.db.set_config("shopify_request_timeout", str(self.request_timeout))
        self.db.set_config("shopify_max_workers", str(self.max_workers))
        self.db.set_config("shopify_max_retries", str(self.max_retries))
        self.db.set_config("shopify_webhook_delay", str(self.webhook_delay))
        self.db.set_config("shopify_detailed_logging", "true" if self.detailed_logging else "false")
        self.db.set_config("shopify_auto_start", "true" if self.auto_start else "false")
        self.db.set_config("shopify_data_collection_mode", "true" if self.data_collection_mode else "false")

        # Save stores and keywords to database
        self._save_stores_keywords()

    def import_from_json(self, json_path: str):
        """Import configuration from a JSON file."""
        if not os.path.exists(json_path):
            return False

        try:
            with open(json_path, 'r') as f:
                config = json.load(f)

            # Map JSON keys to config
            if 'main_webhook' in config:
                self.main_webhook = config['main_webhook']
            if 'singles_webhook' in config:
                self.singles_webhook = config['singles_webhook']
            if 'ignore_singles' in config:
                self.ignore_singles = config['ignore_singles']
            if 'ping_role_id' in config:
                self.ping_role_id = config['ping_role_id']
            if 'ping_enabled' in config:
                self.ping_enabled = config['ping_enabled']
            if 'max_pages' in config:
                self.max_pages = config['max_pages']
            if 'check_interval' in config:
                self.check_interval = config['check_interval']
            if 'request_timeout' in config:
                self.request_timeout = config['request_timeout']
            if 'max_workers' in config:
                self.max_workers = config['max_workers']
            if 'max_retries' in config:
                self.max_retries = config['max_retries']
            if 'webhook_delay' in config:
                self.webhook_delay = config['webhook_delay']
            if 'detailed_logging' in config:
                self.detailed_logging = config['detailed_logging']
            if 'auto_start' in config:
                self.auto_start = config['auto_start']

            self.save_config()
            self.log(f"Imported config from {json_path}")
            return True

        except Exception as e:
            self.log(f"Error importing config: {e}")
            return False

    def _load_stores_keywords(self):
        """Load stores and keywords from database (JSON format)."""
        # Load stores
        self.stores.clear()
        stores_json = self.db.get_config("shopify_stores_json", "[]")
        try:
            self.stores = json.loads(stores_json)
        except Exception:
            self.stores = []

        # Load keywords
        self.keywords.clear()
        keywords_json = self.db.get_config("shopify_keywords_json", "[]")
        try:
            self.keywords = json.loads(keywords_json)
        except Exception:
            self.keywords = []

        self.log(f"Loaded {len(self.stores)} stores, {len(self.keywords)} keywords from database")

    def _save_stores_keywords(self):
        """Save stores and keywords to database (JSON format)."""
        self.db.set_config("shopify_stores_json", json.dumps(self.stores))
        self.db.set_config("shopify_keywords_json", json.dumps(self.keywords))

    def reload_data(self):
        """Reload stores and keywords from database."""
        self._load_stores_keywords()
        # Also reload proxies
        self._load_proxies()
        if self.ui_refresh_callback:
            self.ui_refresh_callback()

    def _init_tracker(self):
        """Initialize the product tracker."""
        tracker_file = os.path.join(self.data_dir, "found.json")
        self.tracker = ProductTracker(tracker_file)

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

        # Rotate through proxies
        proxy = available[self._proxy_index % len(available)]
        self._proxy_index += 1
        return proxy

    def _on_proxy_failure(self, proxy: str):
        """Mark a proxy as failed and rotate to next."""
        if proxy:
            self._failed_proxies.add(proxy)
            self.log(f"Proxy failed: {proxy}")

    def _fetch_products(self, store: str, page: int = 1) -> Optional[List[Dict]]:
        """Fetch products from a Shopify store using Storefront API."""
        # Build GraphQL query
        query = """
        query getProducts($cursor: String, $pageSize: Int!) {
            products(first: $pageSize, after: $cursor) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        id
                        title
                        handle
                        productType
                        vendor
                        tags
                        images(first: 5) {
                            edges {
                                node {
                                    url
                                }
                            }
                        }
                        variants(first: 50) {
                            edges {
                                node {
                                    id
                                    title
                                    price
                                    availableForSale
                                    quantityAvailable
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        url = f"https://{store}/products.json?page={page}&limit=250"

        for attempt in range(self.max_retries):
            proxy = self._get_proxy()

            try:
                response = requests.get(
                    url,
                    timeout=self.request_timeout,
                    proxies={"http": proxy, "https": proxy} if proxy else None
                )

                if response.status_code == 200:
                    data = response.json()
                    products = data.get('products', [])
                    if products:
                        # Transform to consistent format
                        transformed = []
                        for p in products:
                            variants = []
                            for v in p.get('variants', []):
                                variants.append({
                                    'id': v.get('id'),
                                    'title': v.get('title'),
                                    'price': v.get('price', ''),
                                    'available': v.get('available_for_sale', False),
                                })
                            transformed.append({
                                'id': p.get('id'),
                                'title': p.get('title'),
                                'handle': p.get('handle'),
                                'productType': p.get('product_type'),
                                'vendor': p.get('vendor'),
                                'tags': p.get('tags', []),
                                'image': p.get('images', [{}])[0] if p.get('images') else None,
                                'variants': variants,
                            })
                        return transformed
                    return []
                elif response.status_code == 404:
                    return None
                else:
                    self.log(f"Error fetching {store}: HTTP {response.status_code}")
                    # Mark proxy as failed if we got a bad response
                    if proxy:
                        self._on_proxy_failure(proxy)
            except requests.exceptions.Timeout:
                self.log(f"Timeout fetching {store} (attempt {attempt + 1}/{self.max_retries})")
            except Exception as e:
                self.log(f"Error fetching {store}: {e}")

            if attempt < self.max_retries - 1:
                time.sleep(1)

        return None

    def start(self):
        """Start the Shopify monitor."""
        if self._running:
            return

        self._running = True
        self._stop_flag.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self.log("Shopify Monitor started")

    def stop(self):
        """Stop the Shopify monitor."""
        self._running = False
        self._stop_flag.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.log("Shopify Monitor stopped")

    def _monitor_loop(self):
        """Main monitoring loop."""
        # Load proxies at startup
        self._load_proxies()

        if not self.stores:
            self.log("No stores configured - please add stores in settings")

        if not self.keywords:
            self.log("No keywords configured - please add keywords in settings")

        if self.data_collection_mode:
            self.log("Running in DATA COLLECTION MODE (webhooks disabled)")
        elif not self.main_webhook and not self.singles_webhook:
            self.log("Running in DATA COLLECTION MODE (no webhooks configured)")

        if self._proxies:
            self.log(f"Using {len(self._proxies)} proxies with {self.max_workers} workers")
        else:
            self.log(f"Using {self.max_workers} workers (no proxies)")

        while not self._stop_flag.is_set():
            self.log("Starting check cycle...")
            cycle_start = time.time()

            # Check stores concurrently
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
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
            self.log(f"Cycle completed in {cycle_duration:.1f}s")

            # Save tracker
            self.tracker.save()

            # Wait for next cycle
            self.log(f"Waiting {self.check_interval}s...")
            for _ in range(self.check_interval):
                if self._stop_flag.is_set():
                    break
                time.sleep(1)

    def _check_store(self, store: str):
        """Check a single store for matching products."""
        if self.detailed_logging:
            self.log(f"Checking: {store}")

        products_found = 0
        pages_checked = 0

        for page in range(1, self.max_pages + 1):
            if self._stop_flag.is_set():
                break

            products = self._fetch_products(store, page)

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

        if self.detailed_logging and pages_checked > 0:
            self.log(f"{store}: {products_found} products, {pages_checked} pages")

    def _process_product(self, store: str, product: Dict):
        """Process a single product."""
        # Check for keyword matches
        title_lower = product.get('title', '').lower()
        tags_lower = ' '.join(product.get('tags', [])).lower()
        product_type_lower = product.get('productType', '').lower()

        matched_keywords = []
        for k in self.keywords:
            if k in title_lower or k in tags_lower or k in product_type_lower:
                matched_keywords.append(k)

        if not matched_keywords:
            return

        # Use ProductFilter to check if should be monitored
        if not ProductFilter.should_monitor(product):
            if self.detailed_logging:
                self.log(f"Filtered: {product.get('title', '')[:40]}")
            return

        # Detect if it's a single (for webhook routing)
        is_single = ProductFilter.is_card_single(product)

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
    ):
        """Send Discord notification for a product."""
        # Check data collection mode first
        if self.data_collection_mode:
            if self.detailed_logging:
                ptype = "SINGLE" if is_single else "product"
                self.log(f"Tracked {ptype}: {product.get('title', '')[:40]}")
            return

        # Check webhooks
        no_webhooks = not self.main_webhook and not self.singles_webhook

        if no_webhooks:
            if self.detailed_logging:
                ptype = "SINGLE" if is_single else "product"
                self.log(f"Tracked {ptype}: {product.get('title', '')[:40]}")
            return

        # Skip singles if ignored
        if is_single and self.ignore_singles:
            if self.detailed_logging:
                self.log(f"Skipped single: {product.get('title', '')[:40]}")
            return

        # Choose webhook
        if is_single and self.singles_webhook:
            webhook_url = self.singles_webhook
        elif self.main_webhook:
            webhook_url = self.main_webhook
        else:
            return

        # Build notification
        product_url = f"https://{store}/products/{product.get('handle', '')}"

        # Get thumbnail
        thumbnail_url = None
        if product.get('image') and isinstance(product['image'], dict):
            thumbnail_url = product['image'].get('url')
        elif product.get('images') and isinstance(product['images'], list):
            for img in product['images']:
                if isinstance(img, dict) and img.get('url'):
                    thumbnail_url = img['url']
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

        # Build embed
        import discord

        description = ""
        if is_single:
            description = "**SINGLE DETECTED**\n\n"
        description += f"New/updated item from **{store}**"

        color = 0xFF6B6B if is_single else 0x4ECDC4

        fields = [
            {"name": "Store", "value": store, "inline": True},
            {"name": "Keywords", "value": ", ".join(keywords), "inline": True},
            {"name": "Add to Cart", "value": f"[ATC Link]({atc_link})", "inline": True},
        ]

        if variants_text:
            fields.append({"name": "Variants", "value": variants_text, "inline": False})

        success = self._send_webhook(
            webhook_url=webhook_url,
            title=product.get('title', 'Unknown Product'),
            description=description,
            color=color,
            fields=fields,
            thumbnail_url=thumbnail_url,
            url=product_url,
            footer_text="FrontLines - Shopify Monitor"
        )

        if success:
            ptype = "SINGLE" if is_single else "product"
            self.log(f"Notified: {product.get('title', '')[:40]}", "success")
        else:
            self.log(f"Failed to send notification", "error")

    def _send_webhook(
        self,
        webhook_url: str,
        title: str,
        description: str,
        color: int,
        fields: List[Dict],
        thumbnail_url: str = None,
        url: str = None,
        footer_text: str = None
    ) -> bool:
        """Send a Discord webhook."""
        import discord

        try:
            webhook = discord.Webhook.from_url(webhook_url, adapter=discord.AsyncWebhookAdapter(None))

            embed = discord.Embed(
                title=title[:256] if title else title,
                description=description[:4096] if description else description,
                color=discord.Color(color),
                url=url
            )

            for field in fields:
                embed.add_field(
                    name=field.get('name', '')[:256],
                    value=field.get('value', '')[:1024],
                    inline=field.get('inline', False)
                )

            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            if footer_text:
                embed.set_footer(text=footer_text)

            # Send synchronously since we're in a thread
            import requests
            payload = {
                "embeds": [embed.to_dict()]
            }

            # Add role ping if enabled
            if self.ping_enabled and self.ping_role_id:
                payload["content"] = f"<@{self.ping_role_id}>"

            response = requests.post(webhook_url, json=payload, timeout=10)
            return response.status_code in (200, 204)

        except Exception as e:
            self.log(f"Webhook error: {e}")
            return False

    def get_status(self) -> Dict:
        """Get monitor status."""
        return {
            'running': self._running,
            'stores': len(self.stores),
            'keywords': len(self.keywords),
            'tracked': self.tracker.get_stats() if self.tracker else {},
        }
