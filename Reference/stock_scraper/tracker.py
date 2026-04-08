"""
Product Tracker

Tracks seen products to avoid duplicate notifications.
"""

from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import threading
import json


class ProductTracker:
    """Tracks seen products to avoid duplicate notifications.

    Stores product/variant information and determines when to send
    notifications based on:
    - New products (never seen before)
    - Back in stock (was unavailable, now available)
    - Price changes (while available)
    """

    def __init__(self, tracker_file: Path):
        """Initialize tracker.

        Args:
            tracker_file: Path to JSON file for persistence
        """
        self.tracker_file = tracker_file
        self.data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.lock = threading.Lock()
        self.load()

    def load(self) -> None:
        """Load tracked products from file."""
        if not self.tracker_file.exists():
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
                # Ensure parent directory exists
                self.tracker_file.parent.mkdir(parents=True, exist_ok=True)

                with open(self.tracker_file, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, indent=2)
            except Exception as e:
                print(f"[Tracker] Error saving: {e}")

    def update_variant(
        self,
        store: str,
        prod_id: str,
        var_id: str,
        price: str,
        available: bool,
        product_title: str = None
    ) -> bool:
        """Check if we should send a notification for this variant.

        Args:
            store: Store domain
            prod_id: Product ID
            var_id: Variant ID
            price: Variant price
            available: Whether variant is available
            product_title: Product title for tracking

        Returns:
            True if notification should be sent
        """
        with self.lock:
            # Initialize store if needed
            if store not in self.data:
                self.data[store] = {}

            # Initialize product if needed
            if prod_id not in self.data[store]:
                self.data[store][prod_id] = {}

            # Get previous state
            prev_state = self.data[store][prod_id].get(var_id, {})

            # Update current state
            self.data[store][prod_id][var_id] = {
                'price': price,
                'available': available,
                'last_seen': datetime.now().isoformat()
            }

            # Store product title if provided
            if product_title and '_product_title' not in self.data[store][prod_id]:
                self.data[store][prod_id]['_product_title'] = product_title

            # Determine if notification needed:
            # 1. Never seen before
            if not prev_state:
                return True

            # 2. Back in stock
            if not prev_state.get('available') and available:
                return True

            # 3. Price changed while available
            if available and prev_state.get('price') != price:
                return True

            return False

    def get_stats(self) -> Dict:
        """Get tracking statistics.

        Returns:
            Dictionary with tracking stats
        """
        total_stores = len(self.data)
        total_products = sum(len(products) for products in self.data.values())
        total_variants = 0
        for products in self.data.values():
            for variants in products.values():
                # Count actual variants (exclude _product_title)
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
