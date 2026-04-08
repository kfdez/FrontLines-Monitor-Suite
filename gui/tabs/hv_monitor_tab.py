"""HV Monitor tab with Configuration and Products sub-tabs."""
import tkinter as tk
from tkinter import ttk, messagebox


class HVMonitorTab(ttk.Frame):
    """HV Monitor tab with configuration and product management."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._tooltip_window = None
        self._tooltip_timer = None
        self._tooltip_event = None
        self._tooltip_tree = None
        self._last_tooltip_item = None

        # Create notebook for sub-tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Configuration sub-tab
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="Configuration")

        # Products sub-tab
        self.products_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.products_frame, text="Products")

        # Create UI
        self._create_config_ui()
        self._create_products_ui()

        # Load initial data
        self.load_config()

    def _show_tooltip(self, event, tree):
        """Show tooltip on hover with delay."""
        # Get current item
        item = tree.identify_row(event.y)

        # If tooltip is showing for a different item, hide it immediately
        if self._tooltip_window and item != self._last_tooltip_item:
            if self._tooltip_window:
                self._tooltip_window.destroy()
                self._tooltip_window = None
            self._last_tooltip_item = None

        if self._tooltip_timer:
            self.after_cancel(self._tooltip_timer)
            self._tooltip_timer = None

        if not item:
            return

        self._tooltip_event = event
        self._tooltip_tree = tree
        self._tooltip_event_item = item

        self._tooltip_timer = self.after(600, lambda: self._display_tooltip(tree))

    def _display_tooltip(self, tree):
        """Display the tooltip after delay."""
        event = self._tooltip_event
        if not event:
            return

        item = tree.identify_row(event.y)
        if not item:
            return

        # Check if we're still on the same item
        if hasattr(self, '_tooltip_event_item') and item != self._tooltip_event_item:
            return

        column = tree.identify_column(event.x)
        if not column:
            return

        values = tree.item(item, "values")
        col_idx = int(column[1:]) - 1
        if col_idx < 0 or col_idx >= len(values):
            return

        value = values[col_idx]
        if not value:
            return

        self._tooltip_window = tk.Toplevel(tree)
        self._tooltip_window.wm_overrideredirect(True)
        x = tree.winfo_rootx() + event.x + 15
        y = tree.winfo_rooty() + event.y + 10
        self._tooltip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self._tooltip_window, text=value, background="#ffffe0", relief="solid", borderwidth=1, padx=5, pady=2)
        label.pack()

        self._last_tooltip_item = item

    def _hide_tooltip(self, event=None):
        """Hide tooltip."""
        if self._tooltip_timer:
            self.after_cancel(self._tooltip_timer)
            self._tooltip_timer = None
        self._tooltip_event = None
        self._tooltip_tree = None
        if hasattr(self, '_tooltip_event_item'):
            self._tooltip_event_item = None
        self._last_tooltip_item = None

        if self._tooltip_window:
            self._tooltip_window.destroy()
            self._tooltip_window = None

    def _create_config_ui(self):
        """Create the configuration tab UI."""
        # Shopify API Settings
        api_frame = ttk.LabelFrame(self.config_frame, text="Shopify API", padding=10)
        api_frame.pack(fill="x", padx=10, pady=5)

        # Store GraphQL URL
        url_frame = ttk.Frame(api_frame)
        url_frame.pack(fill="x", pady=2)
        ttk.Label(url_frame, text="Store GraphQL URL:", width=22).pack(side=tk.LEFT)
        self.store_url_var = tk.StringVar()
        ttk.Entry(url_frame, textvariable=self.store_url_var, width=50).pack(side=tk.LEFT, fill="x", expand=True)

        # Storefront Token
        token_frame = ttk.Frame(api_frame)
        token_frame.pack(fill="x", pady=2)
        ttk.Label(token_frame, text="Storefront Access Token:", width=22).pack(side=tk.LEFT)
        self.token_var = tk.StringVar()
        ttk.Entry(token_frame, textvariable=self.token_var, width=50, show="*").pack(side=tk.LEFT, fill="x", expand=True)

        # Discord Settings
        discord_frame = ttk.LabelFrame(self.config_frame, text="Discord Settings", padding=10)
        discord_frame.pack(fill="x", padx=10, pady=5)

        # Webhook URL
        webhook_frame = ttk.Frame(discord_frame)
        webhook_frame.pack(fill="x", pady=2)
        ttk.Label(webhook_frame, text="Webhook URL:", width=22).pack(side=tk.LEFT)
        self.webhook_var = tk.StringVar()
        ttk.Entry(webhook_frame, textvariable=self.webhook_var, width=50).pack(side=tk.LEFT, fill="x", expand=True)

        # Role ID
        role_frame = ttk.Frame(discord_frame)
        role_frame.pack(fill="x", pady=2)
        ttk.Label(role_frame, text="Role ID (for pings):", width=22).pack(side=tk.LEFT)
        self.role_id_var = tk.StringVar()
        ttk.Entry(role_frame, textvariable=self.role_id_var, width=30).pack(side=tk.LEFT)

        # Ping enabled checkbox
        self.ping_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(
            discord_frame,
            text="Enable role pings on stock alerts",
            variable=self.ping_enabled_var
        ).pack(anchor="w", pady=2)

        # Monitor Settings
        monitor_frame = ttk.LabelFrame(self.config_frame, text="Monitor Settings", padding=10)
        monitor_frame.pack(fill="x", padx=10, pady=5)

        # Check interval
        interval_frame = ttk.Frame(monitor_frame)
        interval_frame.pack(fill="x", pady=2)
        ttk.Label(interval_frame, text="Check Interval (seconds):", width=22).pack(side=tk.LEFT)
        self.interval_var = tk.IntVar(value=30)
        self.interval_spin = ttk.Spinbox(interval_frame, from_=10, to=300, width=10, textvariable=self.interval_var)
        self.interval_spin.pack(side=tk.LEFT)

        # Auto-start checkbox
        self.auto_start_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            monitor_frame,
            text="Auto-start when application launches",
            variable=self.auto_start_var
        ).pack(anchor="w", pady=5)

        # Save button
        button_frame = ttk.Frame(self.config_frame)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(
            button_frame,
            text="Save Configuration",
            command=self.save_config
        ).pack(side=tk.LEFT, padx=5)

    def _create_products_ui(self):
        """Create the products tab UI."""
        # Products list
        list_frame = ttk.LabelFrame(self.products_frame, text="Monitored Products", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Treeview for products
        columns = ("ID", "Name", "Ping")
        self.products_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        self.products_tree.heading("ID", text="Product/Variant ID")
        self.products_tree.heading("Name", text="Name")
        self.products_tree.heading("Ping", text="Ping")
        self.products_tree.column("ID", width=300)
        self.products_tree.column("Name", width=300)
        self.products_tree.column("Ping", width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.products_tree.yview)
        self.products_tree.configure(yscrollcommand=scrollbar.set)

        self.products_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Tooltip bindings
        self.products_tree.bind("<Motion>", lambda e: self._show_tooltip(e, self.products_tree))
        self.products_tree.bind("<Leave>", self._hide_tooltip)

        # Load products
        self.refresh_products()

        # Action buttons
        btn_frame = ttk.Frame(self.products_frame)
        btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(btn_frame, text="Add by ID", command=self._add_by_id).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Search Products", command=self._open_search).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Remove Selected", command=self._remove_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Toggle Ping", command=self._toggle_ping).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Reset Stock", command=self._reset_stock).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_products).pack(side="left", padx=2)

    def load_config(self):
        """Load configuration from database."""
        self.store_url_var.set(self.app.hv_monitor.store_url)
        self.token_var.set(self.app.hv_monitor.token)
        self.webhook_var.set(self.app.hv_monitor.webhook_url)
        self.role_id_var.set(self.app.hv_monitor.role_id)
        self.ping_enabled_var.set(self.app.hv_monitor.ping_enabled)
        self.interval_var.set(self.app.hv_monitor.check_interval)
        self.auto_start_var.set(self.app.hv_monitor.auto_start)
        self.refresh_products()

    def save_config(self):
        """Save configuration to database."""
        self.app.hv_monitor.store_url = self.store_url_var.get()
        self.app.hv_monitor.token = self.token_var.get()
        self.app.hv_monitor.webhook_url = self.webhook_var.get()
        self.app.hv_monitor.role_id = self.role_id_var.get()
        self.app.hv_monitor.ping_enabled = self.ping_enabled_var.get()
        self.app.hv_monitor.check_interval = self.interval_var.get()
        self.app.hv_monitor.auto_start = self.auto_start_var.get()

        self.app.hv_monitor.save_config()
        messagebox.showinfo("Saved", "Configuration saved successfully.")

    def refresh_products(self):
        """Refresh the products list display."""
        # Clear existing
        for item in self.products_tree.get_children():
            self.products_tree.delete(item)

        # Add products
        for product_id, ping in self.app.hv_monitor.products:
            meta = self.app.hv_monitor.metadata.get(product_id, {})
            name = meta.get('title', '(unknown)')
            ping_str = "Yes" if ping else "No"
            self.products_tree.insert("", "end", values=(product_id, name, ping_str))

    def _add_by_id(self):
        """Open dialog to add product by ID."""
        dialog = tk.Toplevel(self)
        dialog.title("Add Product by ID")
        dialog.geometry("500x180")
        dialog.transient(self)

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Product/Variant ID:").pack(anchor="w")
        product_id_var = tk.StringVar()
        ttk.Entry(frame, textvariable=product_id_var, width=60).pack(fill="x", pady=5)

        ttk.Label(frame, text="Note: Use GraphQL ID like gid://shopify/Product/123456").pack(anchor="w")

        ping_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Enable ping for this product", variable=ping_var).pack(anchor="w", pady=5)

        def add_product():
            product_id = product_id_var.get().strip()
            if not product_id:
                messagebox.showwarning("Error", "Please enter a product ID")
                return

            # Try to fetch product info
            query = self.app.hv_monitor._build_product_query(product_id)
            data = self.app.hv_monitor._graphql_request(query)

            if data and data.get("data", {}).get("node"):
                node = data["data"]["node"]
                if node.get("variants"):
                    # It's a product
                    meta = {"title": node["title"], "type": "product"}
                elif node.get("product"):
                    # It's a variant
                    product = node["product"]
                    meta = {
                        "title": f"{product['title']} - {node['title']}",
                        "price": f"{node['price']['amount']} {node['price']['currencyCode']}",
                        "type": "variant"
                    }
                else:
                    meta = None
            else:
                meta = None

            if self.app.hv_monitor.add_product(product_id, ping_var.get(), meta):
                self.refresh_products()
                dialog.destroy()
            else:
                messagebox.showwarning("Error", "Product already in list")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=10)
        ttk.Button(btn_frame, text="Add", command=add_product).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)

    def _remove_selected(self):
        """Remove selected products."""
        selection = self.products_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select items to remove.")
            return

        if messagebox.askyesno("Confirm", f"Remove {len(selection)} item(s)?"):
            for item in selection:
                values = self.products_tree.item(item, "values")
                product_id = values[0]
                self.app.hv_monitor.remove_product(product_id)

            self.refresh_products()

    def _toggle_ping(self):
        """Toggle ping setting for selected items."""
        selection = self.products_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select items to toggle.")
            return

        for item in selection:
            values = self.products_tree.item(item, "values")
            product_id = values[0]
            self.app.hv_monitor.toggle_product_ping(product_id)

        self.refresh_products()

    def _reset_stock(self):
        """Reset stock status for selected items to trigger alert on next check."""
        selection = self.products_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select items to reset.")
            return

        for item in selection:
            values = self.products_tree.item(item, "values")
            product_id = values[0]
            self.app.hv_monitor.reset_stock_status(product_id)

        self.app.hv_monitor.save_stock_status()
        messagebox.showinfo("Reset", f"Stock status reset for {len(selection)} item(s)")

    def _open_search(self):
        """Open product search dialog."""
        SearchDialog(self, self.app.hv_monitor)


class SearchDialog:
    """Dialog for searching and adding Shopify products."""

    def __init__(self, parent, hv_monitor):
        self.parent = parent
        self.hv_monitor = hv_monitor
        self.results = []

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Product Search")
        self.dialog.transient(parent)

        self._build_ui()

        self.dialog.geometry("800x620")
        self.dialog.minsize(600, 500)
        self.dialog.grab_set()
        self.dialog.focus_set()

    def _build_ui(self):
        """Build the search dialog UI."""
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Search input
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame, width=40)
        self.search_entry.pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 5))
        self.search_entry.bind('<Return>', lambda e: self._search())

        ttk.Button(search_frame, text="Search", command=self._search).pack(side=tk.LEFT)

        # Action buttons — packed BEFORE results_frame so expand=True doesn't consume their space
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", side=tk.BOTTOM, pady=(5, 0))

        self.ping_var = tk.BooleanVar()
        ttk.Checkbutton(btn_frame, text="Enable Ping", variable=self.ping_var).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Add Selected", command=self._add_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Results list — packed last so it fills all remaining space
        results_frame = ttk.LabelFrame(main_frame, text="Results", padding=5)
        results_frame.pack(fill="both", expand=True)

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

        # Tooltip bindings
        self.results_tree.bind("<Motion>", lambda e: self._show_tooltip(e, self.results_tree))
        self.results_tree.bind("<Leave>", self._hide_tooltip)

    def _search(self):
        """Perform product search."""
        keyword = self.search_entry.get().strip()
        if not keyword:
            return

        # Clear results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.results.clear()

        # Check API config
        if not self.hv_monitor.store_url or not self.hv_monitor.token:
            messagebox.showerror("Error", "Please configure Store URL and Token in Configuration tab first.")
            return

        # Search
        try:
            products = self.hv_monitor.search_products(keyword)

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

    def _add_selected(self):
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

            if self.hv_monitor.add_product(result['id'], ping, meta):
                added += 1
            else:
                exists += 1

        msg = f"Added {added} item(s)"
        if exists:
            msg += f"\n{exists} item(s) already in list"

        messagebox.showinfo("Done", msg)
        self.parent.refresh_products()
