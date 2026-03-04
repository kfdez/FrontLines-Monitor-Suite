"""Shopify Monitor tab with Configuration and Monitor sub-tabs."""

import tkinter as tk
from tkinter import ttk, messagebox


class ShopifyMonitorTab(ttk.Frame):
    """Shopify Monitor tab with configuration and monitoring."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Create notebook for sub-tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Monitor sub-tab (first)
        self.monitor_frame = ttk.Frame(self.notebook)
        self.monitor_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.monitor_frame, text="Monitor")

        # Configuration sub-tab
        self.config_frame = ttk.Frame(self.notebook)
        self.config_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.config_frame, text="Configuration")

        # Create UI
        self._create_monitor_ui()
        self._create_config_ui()

        # Load initial data
        self.load_config()

    def _create_monitor_ui(self):
        """Create the monitor tab UI."""
        # Top controls frame (start/stop)
        top_frame = ttk.Frame(self.monitor_frame)
        top_frame.pack(fill="x", padx=10, pady=5)

        self.start_btn = ttk.Button(top_frame, text="Start Monitor", command=self._start_monitor)
        self.start_btn.pack(side="left", padx=2)

        self.stop_btn = ttk.Button(top_frame, text="Stop Monitor", command=self._stop_monitor, state="disabled")
        self.stop_btn.pack(side="left", padx=2)

        ttk.Button(top_frame, text="Refresh Stats", command=self._update_stats).pack(side="left", padx=10)

        # Status label
        self.status_label = ttk.Label(top_frame, text="Status: Stopped")
        self.status_label.pack(side="left", padx=10)

        # Statistics
        stats_frame = ttk.LabelFrame(self.monitor_frame, text="Statistics", padding=10)
        stats_frame.pack(fill="x", padx=10, pady=5)

        self.stats_label = ttk.Label(stats_frame, text="")
        self.stats_label.pack(anchor="w")

        self._update_stats()

        # Activity Log
        log_frame = ttk.LabelFrame(self.monitor_frame, text="Activity Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(log_frame, height=15, width=50, yscrollcommand=log_scroll.set, state="disabled")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.config(command=self.log_text.yview)

        # Set up log callback
        self.app.shopify_monitor.shopify_log_callback = self._log_message

        self._update_button_states()

    def _create_config_ui(self):
        """Create the configuration tab UI."""
        # Create a canvas with scrollbar for vertical scrolling
        canvas = tk.Canvas(self.config_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.config_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        # Create canvas window - use a large width and let it fill
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Use scrollable_frame as parent for all widgets
        parent = scrollable_frame

        # Set minimum width for scrollable frame
        parent.pack_propagate(False)
        parent.configure(width=1200)

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

        # Actions frame
        actions_frame = ttk.LabelFrame(parent, text="Actions", padding=10)
        actions_frame.pack(fill="x", padx=10, pady=5)

        actions_inner = ttk.Frame(actions_frame)
        actions_inner.pack(fill="x")

        ttk.Button(actions_inner, text="Clear Tracked Products", command=self._clear_tracker).pack(side=tk.LEFT, padx=5)

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
        ttk.Button(button_inner, text="Reload Data", command=self._reload_data).pack(side=tk.LEFT, padx=5)

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

        self._update_stats()
        self._update_button_states()

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
        self._update_stats()
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

    def _reload_data(self):
        """Reload stores and keywords from database."""
        self.app.shopify_monitor.reload_data()
        # Reload the text areas
        sm = self.app.shopify_monitor
        self.stores_text.delete("1.0", tk.END)
        self.stores_text.insert("1.0", '\n'.join(sm.stores))
        self.keywords_text.delete("1.0", tk.END)
        self.keywords_text.insert("1.0", '\n'.join(sm.keywords))
        self._update_stats()
        messagebox.showinfo("Reloaded", "Stores and keywords reloaded from database.")

    def _update_stats(self):
        """Update statistics display."""
        sm = self.app.shopify_monitor
        tracker_stats = sm.tracker.get_stats() if sm.tracker else {}

        stats_text = (
            f"Stores configured: {len(sm.stores)}\n"
            f"Keywords configured: {len(sm.keywords)}\n"
            f"Tracked stores: {tracker_stats.get('stores', 0)}\n"
            f"Tracked products: {tracker_stats.get('products', 0)}\n"
            f"Tracked variants: {tracker_stats.get('variants', 0)}"
        )
        self.stats_label.config(text=stats_text)

    def _update_button_states(self):
        """Update start/stop button states based on monitor status."""
        if self.app.shopify_monitor._running:
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.status_label.config(text="Status: Running")
        else:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.status_label.config(text="Status: Stopped")

    def _start_monitor(self):
        """Start the Shopify monitor."""
        self.app.shopify_monitor.start()
        self._update_button_states()

    def _stop_monitor(self):
        """Stop the Shopify monitor."""
        self.app.shopify_monitor.stop()
        self._update_button_states()

    def _clear_tracker(self):
        """Clear all tracked products to force re-check."""
        if messagebox.askyesno("Clear Tracker", "Clear all tracked products?\n\nThis will reset the stock status for all tracked products, causing them to be re-checked and re-notified on the next scan cycle."):
            self.app.shopify_monitor.tracker.clear()
            self.app.shopify_monitor.tracker.save()
            self._update_stats()
            self.app.shopify_monitor.log("Cleared tracked products - all products will be re-notified on next scan")
            messagebox.showinfo("Cleared", "Tracked products cleared. Products will be re-checked on next scan.")
