"""Shopify Monitor tab with Products and Configuration sub-tabs."""

import tkinter as tk
from tkinter import ttk, messagebox


class ToolTip:
    """Tooltip for tkinter widgets."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self._show)
        self.widget.bind("<Leave>", self._hide)

    def _show(self, event=None):
        # Get the item under the cursor
        x, y, cx, cy = self.widget.bbox(event.x, event.y) if hasattr(event, 'x') else (None, None, None, None)
        if x is None:
            return

        item = self.widget.identify_row(event.y)
        if not item:
            return

        column = self.widget.identify_column(event.x)
        if not column:
            return

        # Get the value at this position
        values = self.widget.item(item, "values")
        col_idx = int(column[1:]) - 1  # Convert #1 to index 0
        if col_idx < len(values):
            value = values[col_idx]
            if value:
                # Create tooltip window
                self.tooltip = tk.Toplevel(self.widget)
                self.tooltip.wm_overrideredirect(True)
                self.tooltip.wm_geometry(f"+{self.widget.winfo_rootx() + event.x + 15}+{self.widget.winfo_rooty() + event.y + 10}")
                label = tk.Label(self.tooltip, text=value, background="#ffffe0", relief="solid", borderwidth=1, padx=5, pady=2)
                label.pack()

    def _hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class ShopifyMonitorTab(ttk.Frame):
    """Shopify Monitor tab with products and configuration."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Create notebook for sub-tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Bind tab change to refresh config data
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Products sub-tab (first)
        self.products_frame = ttk.Frame(self.notebook)
        self.products_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.products_frame, text="Products")

        # Configuration sub-tab
        self.config_frame = ttk.Frame(self.notebook)
        self.config_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.config_frame, text="Configuration")

        # Create UI
        self._create_products_ui()
        self._create_config_ui()

        # Load initial data
        self.load_config()

    def _create_products_ui(self):
        """Create the products tab UI."""
        # Top frame for search and actions
        top_frame = ttk.Frame(self.products_frame)
        top_frame.pack(fill="x", padx=10, pady=5)

        # Search bar
        ttk.Label(top_frame, text="Search:").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search)
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=(0, 10))

        # Reset selected button
        ttk.Button(top_frame, text="Reset Selected Stock Status", command=self._reset_selected).pack(side="left", padx=5)

        # Clear all button
        ttk.Button(top_frame, text="Clear All", command=self._clear_all).pack(side="left", padx=5)

        # Refresh button
        ttk.Button(top_frame, text="Refresh", command=self._refresh_products).pack(side="left", padx=5)

        # Products treeview
        tree_frame = ttk.Frame(self.products_frame)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        y_scroll.pack(side="right", fill="y")

        x_scroll = ttk.Scrollbar(tree_frame, orient="horizontal")
        x_scroll.pack(side="bottom", fill="x")

        # Treeview
        columns = ("store", "product", "keywords", "status", "price", "last_seen")
        self.products_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                          yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.config(command=self.products_tree.yview)
        x_scroll.config(command=self.products_tree.xview)

        self.products_tree.heading("store", text="Store", command=lambda: self._sort("store"))
        self.products_tree.heading("product", text="Product", command=lambda: self._sort("product"))
        self.products_tree.heading("keywords", text="Keywords", command=lambda: self._sort("keywords"))
        self.products_tree.heading("status", text="Status", command=lambda: self._sort("status"))
        self.products_tree.heading("price", text="Price", command=lambda: self._sort("price"))
        self.products_tree.heading("last_seen", text="Last Seen", command=lambda: self._sort("last_seen"))

        self.products_tree.column("store", width=150)
        self.products_tree.column("product", width=250)
        self.products_tree.column("keywords", width=150)
        self.products_tree.column("status", width=80)
        self.products_tree.column("price", width=80)
        self.products_tree.column("last_seen", width=150)

        self.products_tree.pack(fill="both", expand=True)

        # Bind double-click to reset
        self.products_tree.bind("<Double-1>", lambda e: self._reset_selected())

        # Add tooltip for hover
        self._tooltip_window = None
        self._tooltip_timer = None
        self._tooltip_event = None
        self._tooltip_data = {}
        self._last_tooltip_item = None
        self.products_tree.bind("<Motion>", self._show_tooltip)
        self.products_tree.bind("<Leave>", self._hide_tooltip)

        # Load products
        self._refresh_products()

    def _show_tooltip(self, event):
        """Show tooltip on hover with delay."""
        # Get current item
        item = self.products_tree.identify_row(event.y)

        # If tooltip is showing for a different item, hide it immediately
        if self._tooltip_window and item != self._last_tooltip_item:
            if self._tooltip_window:
                self._tooltip_window.destroy()
                self._tooltip_window = None
            self._last_tooltip_item = None

        # Cancel any pending tooltip
        if self._tooltip_timer:
            self.after_cancel(self._tooltip_timer)
            self._tooltip_timer = None

        # If no item under cursor, don't show tooltip
        if not item:
            return

        # Store event for delayed showing
        self._tooltip_event = event
        self._tooltip_event_item = item

        # Set timer to show tooltip after 0.6 seconds
        self._tooltip_timer = self.after(600, self._display_tooltip)

    def _display_tooltip(self):
        """Display the tooltip after delay."""
        event = self._tooltip_event
        if not event:
            return

        # Get the item under the cursor
        item = self.products_tree.identify_row(event.y)
        if not item:
            return

        # Check if we're still on the same item that triggered the timer
        if hasattr(self, '_tooltip_event_item') and item != self._tooltip_event_item:
            return

        column = self.products_tree.identify_column(event.x)
        if not column:
            return

        col_idx = int(column[1:]) - 1  # Convert #1 to index 0
        if col_idx < 0:
            return

        # Get full data for tooltip if available
        full_data = self._tooltip_data.get(item, {})
        value = None

        # Column 1 = Product, Column 2 = Keywords
        if col_idx == 1 and full_data.get('product'):
            value = full_data['product']
        elif col_idx == 2 and full_data.get('keywords'):
            value = full_data['keywords']
        else:
            # Fall back to tree values
            values = self.products_tree.item(item, "values")
            if col_idx < len(values):
                value = values[col_idx]

        if not value:
            return

        # Create tooltip window
        self._tooltip_window = tk.Toplevel(self.products_tree)
        self._tooltip_window.wm_overrideredirect(True)
        x = self.products_tree.winfo_rootx() + event.x + 15
        y = self.products_tree.winfo_rooty() + event.y + 10
        self._tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self._tooltip_window, text=value, background="#ffffe0", relief="solid", borderwidth=1, padx=5, pady=2)
        label.pack()

        # Track this item so we can hide when moving to different item
        self._last_tooltip_item = item

    def _hide_tooltip(self, event=None):
        """Hide tooltip."""
        # Cancel any pending tooltip
        if self._tooltip_timer:
            self.after_cancel(self._tooltip_timer)
            self._tooltip_timer = None
        self._tooltip_event = None
        if hasattr(self, '_tooltip_event_item'):
            self._tooltip_event_item = None
        self._last_tooltip_item = None

        if self._tooltip_window:
            self._tooltip_window.destroy()
            self._tooltip_window = None

    def _refresh_products(self):
        """Refresh the products list."""
        self.products_tree.delete(*self.products_tree.get_children())
        # Clear tooltip data mapping
        self._tooltip_data = {}

        sm = self.app.shopify_monitor
        if not sm or not sm.tracker:
            return

        search_term = self.search_var.get().lower()

        # Get tracker data
        for store, products in sm.tracker.data.items():
            for prod_id, variants in products.items():
                if prod_id.startswith('_'):
                    continue

                product_title = variants.get('_product_title', 'Unknown')
                keywords = variants.get('_keywords', [])

                # Filter by search
                if search_term and search_term not in store.lower() and search_term not in product_title.lower() and not any(search_term in k.lower() for k in keywords):
                    continue

                for var_id, data in variants.items():
                    if var_id.startswith('_'):
                        continue

                    status = "In Stock" if data.get('available') else "Out of Stock"
                    price = data.get('price', 'N/A')
                    last_seen = data.get('last_seen', 'N/A')
                    keywords_str = ", ".join(keywords) if keywords else ""

                    # Insert with truncated display but store full data for tooltip
                    item_id = self.products_tree.insert("", "end", values=(
                        store,
                        product_title[:50] + "..." if len(product_title) > 50 else product_title,
                        keywords_str,
                        status,
                        price,
                        last_seen[:19] if len(last_seen) > 19 else last_seen
                    ))
                    # Store full data for tooltip
                    self._tooltip_data[item_id] = {
                        'product': product_title,
                        'keywords': keywords_str,
                        'store': store
                    }

    def _on_search(self, *args):
        """Handle search input."""
        self._refresh_products()

    def _sort(self, column):
        """Sort tree by column."""
        # Get all items
        items = []
        for item in self.products_tree.get_children(""):
            values = self.products_tree.item(item, "values")
            items.append((values, item))

        # Sort based on column
        col_index = ("store", "product", "keywords", "status", "price", "last_seen").index(column)
        try:
            items.sort(key=lambda x: x[0][col_index].lower())
        except:
            items.sort(key=lambda x: x[0][col_index])

        # Re-insert in sorted order
        for values, item in items:
            self.products_tree.move(item, "", "end")

    def _reset_selected(self):
        """Reset stock status for selected product."""
        selection = self.products_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a product to reset.")
            return

        if not messagebox.askyesno("Reset Stock Status", "Reset stock status for selected product(s)?\n\nThis will allow them to be notified again on the next scan."):
            return

        sm = self.app.shopify_monitor
        if not sm or not sm.tracker:
            return

        reset_count = 0
        for item in selection:
            values = self.products_tree.item(item, "values")
            store = values[0]
            product_title = values[1]

            # Find and reset matching variants
            if store in sm.tracker.data:
                for prod_id, variants in sm.tracker.data[store].items():
                    if variants.get('_product_title', '').endswith('...'):
                        stored_title = variants.get('_product_title', '')[:-3]
                    else:
                        stored_title = variants.get('_product_title', '')

                    if stored_title == product_title or product_title.startswith(stored_title[:20]):
                        for var_id in list(variants.keys()):
                            if not var_id.startswith('_'):
                                variants[var_id]['available'] = False
                                reset_count += 1

        if reset_count > 0:
            sm.tracker.save()
            self._refresh_products()
            messagebox.showinfo("Reset", f"Reset {reset_count} variant(s).")
        else:
            messagebox.showwarning("Not Found", "Could not find matching product in tracker.")

    def _clear_all(self):
        """Clear all tracked products."""
        if not messagebox.askyesno("Clear All", "Clear all tracked products?\n\nThis will reset the stock status for ALL tracked products."):
            return

        sm = self.app.shopify_monitor
        if sm and sm.tracker:
            sm.tracker.clear()
            sm.tracker.save()
            self._refresh_products()
            messagebox.showinfo("Cleared", "All tracked products cleared.")


    def _create_config_ui(self):
        """Create the configuration tab UI."""
        # Create a canvas with scrollbar for vertical scrolling
        self.canvas = tk.Canvas(self.config_frame)
        scrollbar = ttk.Scrollbar(self.config_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Create canvas window
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind resize event to update canvas width
        self.config_frame.bind("<Configure>", self._on_config_resize)

        # Use scrollable_frame as parent for all widgets
        parent = self.scrollable_frame

        # Discord Settings
        discord_frame = ttk.LabelFrame(parent, text="Discord Settings", padding=10)
        discord_frame.pack(fill="x", padx=10, pady=5)

        # Main Webhook URL
        webhook_frame = ttk.Frame(discord_frame)
        webhook_frame.pack(fill="x", pady=2)
        ttk.Label(webhook_frame, text="Main Webhook URL:").pack(side=tk.LEFT, padx=(0, 10))
        self.main_webhook_var = tk.StringVar()
        ttk.Entry(webhook_frame, textvariable=self.main_webhook_var).pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 10))

        # Singles Webhook URL
        singles_frame = ttk.Frame(discord_frame)
        singles_frame.pack(fill="x", pady=2)
        ttk.Label(singles_frame, text="Singles Webhook URL:").pack(side=tk.LEFT, padx=(0, 10))
        self.singles_webhook_var = tk.StringVar()
        ttk.Entry(singles_frame, textvariable=self.singles_webhook_var).pack(side=tk.LEFT, fill="x", expand=True, padx=(0, 10))

        # Ignore Singles checkbox
        ignore_singles_container = ttk.Frame(discord_frame)
        ignore_singles_container.pack(fill="x", pady=2)
        self.ignore_singles_var = tk.BooleanVar()
        ttk.Checkbutton(
            ignore_singles_container,
            text="Ignore Singles (don't send singles notifications)",
            variable=self.ignore_singles_var
        ).pack(side=tk.LEFT)

        # Role Ping Settings
        ping_frame = ttk.LabelFrame(discord_frame, text="Role Ping Settings", padding=5)
        ping_frame.pack(fill="x", pady=5)

        ping_id_frame = ttk.Frame(ping_frame)
        ping_id_frame.pack(fill="x", pady=2)
        ttk.Label(ping_id_frame, text="Role ID to Ping:").pack(side=tk.LEFT, padx=(0, 10))
        self.ping_role_id_var = tk.StringVar()
        ttk.Entry(ping_id_frame, textvariable=self.ping_role_id_var, width=30).pack(side=tk.LEFT, padx=(0, 20))
        self.ping_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            ping_id_frame,
            text="Enable role pings on notifications",
            variable=self.ping_enabled_var
        ).pack(side=tk.LEFT)

        # Scraping Settings
        scraping_frame = ttk.LabelFrame(parent, text="Scraping Settings", padding=10)
        scraping_frame.pack(fill="x", padx=10, pady=5)

        # Settings row 1
        settings_row1 = ttk.Frame(scraping_frame)
        settings_row1.pack(fill="x", pady=2)

        ttk.Label(settings_row1, text="Check Interval (sec):").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.interval_var = tk.IntVar(value=300)
        ttk.Spinbox(settings_row1, from_=30, to=3600, width=12, textvariable=self.interval_var).grid(row=0, column=1, sticky="w", padx=(0, 20))

        ttk.Label(settings_row1, text="Max Pages:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.max_pages_var = tk.IntVar(value=3)
        ttk.Spinbox(settings_row1, from_=1, to=10, width=8, textvariable=self.max_pages_var).grid(row=0, column=3, sticky="w", padx=(0, 20))

        ttk.Label(settings_row1, text="Workers:").grid(row=0, column=4, sticky="w", padx=(0, 5))
        self.workers_var = tk.IntVar(value=3)
        ttk.Spinbox(settings_row1, from_=1, to=10, width=8, textvariable=self.workers_var).grid(row=0, column=5, sticky="w")

        # Settings row 2
        settings_row2 = ttk.Frame(scraping_frame)
        settings_row2.pack(fill="x", pady=2)

        ttk.Label(settings_row2, text="Timeout (sec):").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.timeout_var = tk.IntVar(value=15)
        ttk.Spinbox(settings_row2, from_=5, to=60, width=12, textvariable=self.timeout_var).grid(row=0, column=1, sticky="w", padx=(0, 20))

        ttk.Label(settings_row2, text="Max Retries:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.retries_var = tk.IntVar(value=3)
        ttk.Spinbox(settings_row2, from_=1, to=10, width=8, textvariable=self.retries_var).grid(row=0, column=3, sticky="w", padx=(0, 20))

        ttk.Label(settings_row2, text="Webhook Delay (s):").grid(row=0, column=4, sticky="w", padx=(0, 5))
        self.webhook_delay_var = tk.DoubleVar(value=0.8)
        ttk.Spinbox(settings_row2, from_=0.1, to=5.0, increment=0.1, width=8, textvariable=self.webhook_delay_var).grid(row=0, column=5, sticky="w")

        # Options
        options_frame = ttk.LabelFrame(parent, text="Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)

        options_inner = ttk.Frame(options_frame)
        options_inner.pack(fill="x")

        self.auto_start_var = tk.BooleanVar()
        ttk.Checkbutton(
            options_inner,
            text="Auto-start when application launches",
            variable=self.auto_start_var
        ).pack(side=tk.LEFT, padx=10)

        self.detailed_log_var = tk.BooleanVar()
        ttk.Checkbutton(
            options_inner,
            text="Detailed logging (verbose scanning output)",
            variable=self.detailed_log_var
        ).pack(side=tk.LEFT, padx=10)

        self.data_collection_var = tk.BooleanVar()
        ttk.Checkbutton(
            options_inner,
            text="Data Collection Mode (run without sending Discord webhooks)",
            variable=self.data_collection_var
        ).pack(side=tk.LEFT, padx=10)

        # Stores and Keywords
        data_frame = ttk.LabelFrame(parent, text="Stores & Keywords", padding=10)
        data_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Use a paned window to split stores and keywords side by side
        stores_keywords_paned = ttk.PanedWindow(data_frame, orient=tk.HORIZONTAL)
        stores_keywords_paned.pack(fill=tk.BOTH, expand=True)

        # Stores
        stores_frame = ttk.Frame(stores_keywords_paned)
        stores_keywords_paned.add(stores_frame, weight=1)
        ttk.Label(stores_frame, text="Stores (one per line):").pack(anchor="w", pady=(0, 5))

        stores_scroll = ttk.Scrollbar(stores_frame)
        stores_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.stores_text = tk.Text(stores_frame, height=8, yscrollcommand=stores_scroll.set)
        self.stores_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        stores_scroll.config(command=self.stores_text.yview)

        # Keywords
        keywords_frame = ttk.Frame(stores_keywords_paned)
        stores_keywords_paned.add(keywords_frame, weight=1)
        ttk.Label(keywords_frame, text="Keywords (one per line):").pack(anchor="w", pady=(0, 5))

        keywords_scroll = ttk.Scrollbar(keywords_frame)
        keywords_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.keywords_text = tk.Text(keywords_frame, height=8, yscrollcommand=keywords_scroll.set)
        self.keywords_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        keywords_scroll.config(command=self.keywords_text.yview)

        # Save/ Test Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", padx=10, pady=10)

        button_inner = ttk.Frame(button_frame)
        button_inner.pack(fill="x")

        ttk.Button(button_inner, text="Save Configuration", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_inner, text="Test Webhook", command=self._test_webhook).pack(side=tk.LEFT, padx=5)

    def _on_config_resize(self, event):
        """Handle resize events to update canvas width."""
        if hasattr(self, 'canvas') and hasattr(self, 'scrollable_frame'):
            # Only update on configure events from the frame, not from canvas children
            if event.widget == self.config_frame:
                width = event.width - 20  # Account for scrollbar
                self.canvas.itemconfig(1, width=max(width, 1000))

    def _log_message(self, message: str):
        """Add a message to the activity log."""
        def update_log():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, f"{message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")

        try:
            self.after(0, update_log)
        except Exception:
            pass

    def load_config(self):
        """Load configuration from monitor."""
        sm = self.app.shopify_monitor

        self.main_webhook_var.set(sm.main_webhook)
        self.singles_webhook_var.set(sm.singles_webhook)
        self.ignore_singles_var.set(sm.ignore_singles)
        self.ping_role_id_var.set(sm.ping_role_id)
        self.ping_enabled_var.set(sm.ping_enabled)
        self.interval_var.set(sm.check_interval)
        self.max_pages_var.set(sm.max_pages)
        self.workers_var.set(sm.max_workers)
        self.timeout_var.set(sm.request_timeout)
        self.retries_var.set(sm.max_retries)
        self.webhook_delay_var.set(sm.webhook_delay)
        self.auto_start_var.set(sm.auto_start)
        self.detailed_log_var.set(sm.detailed_logging)
        self.data_collection_var.set(sm.data_collection_mode)

        # Load stores and keywords into text areas
        self.stores_text.delete("1.0", tk.END)
        self.stores_text.insert("1.0", '\n'.join(sm.stores))

        self.keywords_text.delete("1.0", tk.END)
        self.keywords_text.insert("1.0", '\n'.join(sm.keywords))

    def save_config(self):
        """Save configuration."""
        sm = self.app.shopify_monitor

        sm.main_webhook = self.main_webhook_var.get()
        sm.singles_webhook = self.singles_webhook_var.get()
        sm.ignore_singles = self.ignore_singles_var.get()
        sm.ping_role_id = self.ping_role_id_var.get()
        sm.ping_enabled = self.ping_enabled_var.get()
        sm.check_interval = self.interval_var.get()
        sm.max_pages = self.max_pages_var.get()
        sm.max_workers = self.workers_var.get()
        sm.request_timeout = self.timeout_var.get()
        sm.max_retries = self.retries_var.get()
        sm.webhook_delay = self.webhook_delay_var.get()
        sm.auto_start = self.auto_start_var.get()
        sm.detailed_logging = self.detailed_log_var.get()
        sm.data_collection_mode = self.data_collection_var.get()

        # Parse stores and keywords from text areas
        stores_content = self.stores_text.get("1.0", tk.END).strip()
        sm.stores = [line.strip() for line in stores_content.split('\n') if line.strip()]

        keywords_content = self.keywords_text.get("1.0", tk.END).strip()
        sm.keywords = [line.strip().lower() for line in keywords_content.split('\n') if line.strip()]

        sm.save_config()
        # Update text areas with the saved values (e.g., keywords are lowercased)
        self.stores_text.delete("1.0", tk.END)
        self.stores_text.insert("1.0", '\n'.join(sm.stores))
        self.keywords_text.delete("1.0", tk.END)
        self.keywords_text.insert("1.0", '\n'.join(sm.keywords))
        messagebox.showinfo("Saved", "Configuration saved successfully.")

    def _test_webhook(self):
        """Test Discord webhook."""
        webhook_url = self.main_webhook_var.get()
        if not webhook_url:
            messagebox.showwarning("No Webhook", "Please enter a webhook URL first.")
            return

        import requests
        try:
            payload = {
                "embeds": [{
                    "title": "Test Notification",
                    "description": "This is a test from the Shopify Monitor.",
                    "color": 0x4ECDC4,
                    "footer": {"text": "FrontLines - Shopify Monitor"}
                }]
            }
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code in (200, 204):
                messagebox.showinfo("Success", "Test notification sent!")
            else:
                messagebox.showerror("Failed", f"HTTP {response.status_code}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_tab_changed(self, event=None):
        """Handle tab change - refresh config from database."""
        # Get current tab index (0 = Products, 1 = Configuration)
        current = self.notebook.index(self.notebook.select())
        if current == 1:  # Configuration tab
            # Reload from database to get latest values
            self.app.shopify_monitor.reload_data()
            # Update text areas
            sm = self.app.shopify_monitor
            self.stores_text.delete("1.0", tk.END)
            self.stores_text.insert("1.0", '\n'.join(sm.stores))
            self.keywords_text.delete("1.0", tk.END)
            self.keywords_text.insert("1.0", '\n'.join(sm.keywords))
