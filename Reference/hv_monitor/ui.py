"""
HV Monitor UI

User interface for the HV Monitor module.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING, List, Dict

from frontlines.core.base_ui import BaseModuleUI, LabeledEntry, LabeledSpinbox

if TYPE_CHECKING:
    from frontlines.modules.hv_monitor.module import HVMonitorModule


class HVMonitorUI(BaseModuleUI):
    """UI for the HV Monitor module."""

    def __init__(self, parent: tk.Widget, module: 'HVMonitorModule', **kwargs):
        """Initialize HV Monitor UI."""
        super().__init__(parent, module, **kwargs)
        self._update_info()

    def _build_config_tab(self) -> None:
        """Build the configuration tab."""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="Configuration")

        # API Settings
        api_frame = ttk.LabelFrame(config_frame, text="Shopify API", padding=10)
        api_frame.pack(fill="x", padx=10, pady=5)

        self.store_url_entry = LabeledEntry(api_frame, "Store GraphQL URL:", width=60)
        self.store_url_entry.pack(fill="x", pady=2)
        self.store_url_entry.set(self.module.config.store_url)

        self.token_entry = LabeledEntry(api_frame, "Storefront Access Token:", width=60, show="*")
        self.token_entry.pack(fill="x", pady=2)
        self.token_entry.set(self.module.config.token)

        # Discord Settings
        discord_frame = ttk.LabelFrame(config_frame, text="Discord Settings", padding=10)
        discord_frame.pack(fill="x", padx=10, pady=5)

        self.webhook_entry = LabeledEntry(discord_frame, "Webhook URL:", width=60)
        self.webhook_entry.pack(fill="x", pady=2)
        self.webhook_entry.set(self.module.config.discord_webhook)

        self.role_entry = LabeledEntry(discord_frame, "Role ID (for pings):", width=30)
        self.role_entry.pack(fill="x", pady=2)
        self.role_entry.set(self.module.config.discord_role_id)

        self.ping_var = tk.BooleanVar(value=self.module.config.ping_role)
        ttk.Checkbutton(
            discord_frame,
            text="Always ping role on stock alerts",
            variable=self.ping_var
        ).pack(anchor="w", pady=2)

        # Monitor Settings
        monitor_frame = ttk.LabelFrame(config_frame, text="Monitor Settings", padding=10)
        monitor_frame.pack(fill="x", padx=10, pady=5)

        settings_row = ttk.Frame(monitor_frame)
        settings_row.pack(fill="x", pady=5)

        self.interval_spin = LabeledSpinbox(settings_row, "Check Interval (sec):", from_=10, to=300, width=10)
        self.interval_spin.pack(side="left", padx=5)
        self.interval_spin.set(self.module.config.check_interval)

        self.search_limit_spin = LabeledSpinbox(settings_row, "Search Limit:", from_=5, to=50, width=10)
        self.search_limit_spin.pack(side="left", padx=5)
        self.search_limit_spin.set(self.module.config.search_limit)

        # Options
        options_frame = ttk.LabelFrame(config_frame, text="Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)

        self.auto_start_var = tk.BooleanVar(value=self.module.config.auto_start)
        ttk.Checkbutton(
            options_frame,
            text="Auto-start when application launches",
            variable=self.auto_start_var
        ).pack(anchor="w", pady=2)

        # Save Button
        button_frame = ttk.Frame(config_frame)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(
            button_frame,
            text="Save Configuration",
            command=self._save_config
        ).pack(side="left", padx=5)

    def _build_monitor_tab(self) -> None:
        """Build the monitor/items tab."""
        monitor_frame = ttk.Frame(self.notebook)
        self.notebook.add(monitor_frame, text="Products")

        # Products list
        list_frame = ttk.LabelFrame(monitor_frame, text="Monitored Products", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Treeview for products
        columns = ("ID", "Name", "Ping")
        self.products_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        self.products_tree.heading("ID", text="Product/Variant ID")
        self.products_tree.heading("Name", text="Name")
        self.products_tree.heading("Ping", text="Ping")
        self.products_tree.column("ID", width=300)
        self.products_tree.column("Name", width=300)
        self.products_tree.column("Ping", width=50)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.products_tree.yview)
        self.products_tree.configure(yscrollcommand=scrollbar.set)

        self.products_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Load products
        self._refresh_products_list()

        # Action buttons
        btn_frame = ttk.Frame(monitor_frame)
        btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(btn_frame, text="Search Products", command=self._open_search).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Remove Selected", command=self._remove_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Toggle Ping", command=self._toggle_ping).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_products_list).pack(side="left", padx=2)

    def _on_config(self) -> None:
        """Handle settings button click."""
        self.notebook.select(0)

    def _save_config(self) -> None:
        """Save configuration."""
        self.module.config.store_url = self.store_url_entry.get()
        self.module.config.token = self.token_entry.get()
        self.module.config.discord_webhook = self.webhook_entry.get()
        self.module.config.discord_role_id = self.role_entry.get()
        self.module.config.ping_role = self.ping_var.get()
        self.module.config.check_interval = self.interval_spin.get()
        self.module.config.search_limit = self.search_limit_spin.get()
        self.module.config.auto_start = self.auto_start_var.get()

        self.module.save_config()
        self._update_info()

        messagebox.showinfo("Saved", "Configuration saved successfully.")

    def _update_info(self) -> None:
        """Update status bar info."""
        info = f"Products: {len(self.module.products)} | Interval: {self.module.config.check_interval}s"
        self.status_bar.set_info(info)

    def _refresh_products_list(self) -> None:
        """Refresh the products list display."""
        # Clear existing
        for item in self.products_tree.get_children():
            self.products_tree.delete(item)

        # Add products
        for product_id, ping in self.module.products:
            meta = self.module.metadata.get(product_id, {})
            name = meta.get('title', '(unknown)')
            ping_str = "Yes" if ping else "No"
            self.products_tree.insert("", "end", values=(product_id, name, ping_str))

        self._update_info()

    def _remove_selected(self) -> None:
        """Remove selected products."""
        selection = self.products_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select items to remove.")
            return

        if messagebox.askyesno("Confirm", f"Remove {len(selection)} item(s)?"):
            for item in selection:
                values = self.products_tree.item(item, "values")
                product_id = values[0]
                self.module.remove_product(product_id)

            self._refresh_products_list()

    def _toggle_ping(self) -> None:
        """Toggle ping setting for selected items."""
        selection = self.products_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select items to toggle.")
            return

        for item in selection:
            values = self.products_tree.item(item, "values")
            product_id = values[0]

            # Find and toggle
            for i, (pid, ping) in enumerate(self.module.products):
                if pid == product_id:
                    self.module.products[i] = (pid, not ping)
                    break

        self.module._save_products()
        self._refresh_products_list()

    def _open_search(self) -> None:
        """Open product search dialog."""
        SearchDialog(self, self.module)


class SearchDialog:
    """Dialog for searching and adding products."""

    def __init__(self, parent: HVMonitorUI, module: 'HVMonitorModule'):
        self.parent = parent
        self.module = module
        self.results: List[Dict] = []

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Product Search")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the search dialog UI."""
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Search input
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side="left", padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame, width=40)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.search_entry.bind('<Return>', lambda e: self._search())

        ttk.Button(search_frame, text="Search", command=self._search).pack(side="left")

        # Results list
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding=5)
        results_frame.pack(fill="both", expand=True, pady=(0, 10))

        columns = ("Type", "Title", "Price", "Available")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=15)
        self.results_tree.heading("Type", text="Type")
        self.results_tree.heading("Title", text="Title")
        self.results_tree.heading("Price", text="Price")
        self.results_tree.heading("Available", text="Available")
        self.results_tree.column("Type", width=80)
        self.results_tree.column("Title", width=350)
        self.results_tree.column("Price", width=100)
        self.results_tree.column("Available", width=80)

        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        self.results_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Action buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x")

        self.ping_var = tk.BooleanVar()
        ttk.Checkbutton(btn_frame, text="Enable Ping", variable=self.ping_var).pack(side="left", padx=5)

        ttk.Button(btn_frame, text="Add Selected", command=self._add_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side="right", padx=5)

    def _search(self) -> None:
        """Perform search."""
        keyword = self.search_entry.get().strip()
        if not keyword:
            return

        # Clear results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.results.clear()

        # Search
        try:
            products = self.module.search_products(keyword)

            for product in products:
                # Add product
                self.results.append({
                    'type': 'product',
                    'id': product['id'],
                    'data': product
                })
                self.results_tree.insert("", "end", values=(
                    "Product",
                    product['title'][:50],
                    "",
                    "Yes" if product['availableForSale'] else "No"
                ))

                # Add variants
                for v in product.get("variants", {}).get("edges", []):
                    variant = v["node"]
                    self.results.append({
                        'type': 'variant',
                        'id': variant['id'],
                        'data': variant,
                        'product': product
                    })
                    price = f"{variant['price']['amount']} {variant['price']['currencyCode']}"
                    self.results_tree.insert("", "end", values=(
                        "  Variant",
                        f"  {variant['title'][:45]}",
                        price,
                        "Yes" if variant['availableForSale'] else "No"
                    ))

            if not products:
                messagebox.showinfo("No Results", "No products found.")

        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")

    def _add_selected(self) -> None:
        """Add selected items to monitor list."""
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select items to add.")
            return

        ping = self.ping_var.get()
        added = 0
        exists = 0

        for item in selection:
            idx = self.results_tree.index(item)
            if idx >= len(self.results):
                continue

            result = self.results[idx]

            # Build metadata
            if result['type'] == 'product':
                product = result['data']
                meta = {'title': product['title'], 'type': 'product'}
            else:
                variant = result['data']
                product = result['product']
                meta = {
                    'title': f"{product['title']} - {variant['title']}",
                    'price': f"{variant['price']['amount']} {variant['price']['currencyCode']}",
                    'type': 'variant'
                }

            if self.module.add_product(result['id'], ping, meta):
                added += 1
            else:
                exists += 1

        msg = f"Added {added} item(s)"
        if exists:
            msg += f"\n{exists} item(s) already in list"

        messagebox.showinfo("Done", msg)
        self.parent._refresh_products_list()
