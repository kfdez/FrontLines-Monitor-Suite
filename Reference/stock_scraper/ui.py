"""
Stock Scraper UI

User interface for the Stock Scraper module.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import TYPE_CHECKING

from frontlines.core.base_ui import BaseModuleUI, LabeledEntry, LabeledSpinbox

if TYPE_CHECKING:
    from frontlines.modules.stock_scraper.module import StockScraperModule


class StockScraperUI(BaseModuleUI):
    """UI for the Stock Scraper module."""

    def __init__(self, parent: tk.Widget, module: 'StockScraperModule', **kwargs):
        """Initialize Stock Scraper UI."""
        super().__init__(parent, module, **kwargs)

        # Update status bar info
        self._update_info()

    def _build_config_tab(self) -> None:
        """Build the configuration tab."""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="Configuration")

        # Create scrollable frame
        canvas = tk.Canvas(config_frame)
        scrollbar = ttk.Scrollbar(config_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Discord Settings
        discord_frame = ttk.LabelFrame(scrollable_frame, text="Discord Settings", padding=10)
        discord_frame.pack(fill="x", padx=10, pady=5)

        self.main_webhook_entry = LabeledEntry(discord_frame, "Main Webhook URL:", width=60)
        self.main_webhook_entry.pack(fill="x", pady=2)
        self.main_webhook_entry.set(self.module.config.main_webhook)

        self.singles_webhook_entry = LabeledEntry(discord_frame, "Singles Webhook URL:", width=60)
        self.singles_webhook_entry.pack(fill="x", pady=2)
        self.singles_webhook_entry.set(self.module.config.singles_webhook)

        self.ignore_singles_var = tk.BooleanVar(value=self.module.config.ignore_singles)
        ttk.Checkbutton(
            discord_frame,
            text="Ignore Singles (don't send singles notifications)",
            variable=self.ignore_singles_var
        ).pack(anchor="w", pady=2)

        # Scraping Settings
        scraping_frame = ttk.LabelFrame(scrollable_frame, text="Scraping Settings", padding=10)
        scraping_frame.pack(fill="x", padx=10, pady=5)

        settings_row = ttk.Frame(scraping_frame)
        settings_row.pack(fill="x", pady=5)

        self.interval_spin = LabeledSpinbox(settings_row, "Check Interval (sec):", from_=30, to=3600, width=10)
        self.interval_spin.pack(side="left", padx=5)
        self.interval_spin.set(self.module.config.check_interval)

        self.max_pages_spin = LabeledSpinbox(settings_row, "Max Pages:", from_=1, to=10, width=10)
        self.max_pages_spin.pack(side="left", padx=5)
        self.max_pages_spin.set(self.module.config.max_pages)

        self.workers_spin = LabeledSpinbox(settings_row, "Workers:", from_=1, to=10, width=10)
        self.workers_spin.pack(side="left", padx=5)
        self.workers_spin.set(self.module.config.max_workers)

        self.timeout_spin = LabeledSpinbox(settings_row, "Timeout (sec):", from_=5, to=60, width=10)
        self.timeout_spin.pack(side="left", padx=5)
        self.timeout_spin.set(self.module.config.request_timeout)

        # Options
        options_frame = ttk.LabelFrame(scrollable_frame, text="Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)

        self.auto_start_var = tk.BooleanVar(value=self.module.config.auto_start)
        ttk.Checkbutton(
            options_frame,
            text="Auto-start when application launches",
            variable=self.auto_start_var
        ).pack(anchor="w", pady=2)

        self.detailed_log_var = tk.BooleanVar(value=self.module.config.detailed_logging)
        ttk.Checkbutton(
            options_frame,
            text="Detailed logging (verbose scanning output)",
            variable=self.detailed_log_var
        ).pack(anchor="w", pady=2)

        # Data Files
        files_frame = ttk.LabelFrame(scrollable_frame, text="Data Files", padding=10)
        files_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(files_frame, text=f"Data directory: {self.module.data_path}").pack(anchor="w")

        file_buttons = ttk.Frame(files_frame)
        file_buttons.pack(fill="x", pady=5)

        ttk.Button(
            file_buttons,
            text="Edit Stores",
            command=self._edit_stores
        ).pack(side="left", padx=2)

        ttk.Button(
            file_buttons,
            text="Edit Keywords",
            command=self._edit_keywords
        ).pack(side="left", padx=2)

        ttk.Button(
            file_buttons,
            text="Reload Data",
            command=self._reload_data
        ).pack(side="left", padx=2)

        # Save Button
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(
            button_frame,
            text="Save Configuration",
            command=self._save_config
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame,
            text="Test Webhook",
            command=self._test_webhook
        ).pack(side="left", padx=5)

    def _build_monitor_tab(self) -> None:
        """Build the monitor tab."""
        monitor_frame = ttk.Frame(self.notebook)
        self.notebook.add(monitor_frame, text="Monitor")

        # Stats frame
        stats_frame = ttk.LabelFrame(monitor_frame, text="Statistics", padding=10)
        stats_frame.pack(fill="x", padx=10, pady=5)

        self.stats_label = ttk.Label(stats_frame, text="")
        self.stats_label.pack(anchor="w")

        # Refresh stats
        self._update_stats()

        ttk.Button(
            stats_frame,
            text="Refresh",
            command=self._update_stats
        ).pack(anchor="w", pady=5)

        # Quick actions
        actions_frame = ttk.LabelFrame(monitor_frame, text="Quick Actions", padding=10)
        actions_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(
            actions_frame,
            text="Clear Tracked Products",
            command=self._clear_tracker
        ).pack(side="left", padx=5)

        ttk.Button(
            actions_frame,
            text="Reload Proxies",
            command=self._reload_proxies
        ).pack(side="left", padx=5)

    def _on_config(self) -> None:
        """Handle settings button click."""
        # Switch to config tab
        self.notebook.select(0)

    def _save_config(self) -> None:
        """Save configuration."""
        # Update config from UI
        self.module.config.main_webhook = self.main_webhook_entry.get()
        self.module.config.singles_webhook = self.singles_webhook_entry.get()
        self.module.config.ignore_singles = self.ignore_singles_var.get()
        self.module.config.check_interval = self.interval_spin.get()
        self.module.config.max_pages = self.max_pages_spin.get()
        self.module.config.max_workers = self.workers_spin.get()
        self.module.config.request_timeout = self.timeout_spin.get()
        self.module.config.auto_start = self.auto_start_var.get()
        self.module.config.detailed_logging = self.detailed_log_var.get()

        # Save
        self.module.save_config()
        self._update_info()

        messagebox.showinfo("Saved", "Configuration saved successfully.")

    def _test_webhook(self) -> None:
        """Test Discord webhook."""
        webhook_url = self.main_webhook_entry.get()
        if not webhook_url:
            messagebox.showwarning("No Webhook", "Please enter a webhook URL first.")
            return

        success = self.module.services.discord.send_embed(
            webhook_url=webhook_url,
            title="Test Notification",
            description="This is a test from the Stock Scraper module.",
            color=0x4ECDC4,
            footer_text="FrontLines - Stock Scraper"
        )

        if success:
            messagebox.showinfo("Success", "Test notification sent!")
        else:
            messagebox.showerror("Failed", "Failed to send test notification.")

    def _edit_stores(self) -> None:
        """Open stores file in default editor."""
        import subprocess
        import os
        stores_file = self.module.data_path / "stores.txt"
        if os.name == 'nt':  # Windows
            os.startfile(stores_file)
        else:
            subprocess.run(['xdg-open', stores_file])

    def _edit_keywords(self) -> None:
        """Open keywords file in default editor."""
        import subprocess
        import os
        keywords_file = self.module.data_path / "keywords.txt"
        if os.name == 'nt':  # Windows
            os.startfile(keywords_file)
        else:
            subprocess.run(['xdg-open', keywords_file])

    def _reload_data(self) -> None:
        """Reload stores and keywords."""
        self.module.reload_data()
        self._update_info()
        self._update_stats()
        messagebox.showinfo("Reloaded", "Stores and keywords reloaded.")

    def _update_info(self) -> None:
        """Update status bar info."""
        webhook_ok = bool(self.module.config.main_webhook)
        singles_ok = bool(self.module.config.singles_webhook)

        if self.module.config.ignore_singles:
            singles_status = "ignored"
        elif singles_ok:
            singles_status = "configured"
        else:
            singles_status = "not set"

        info = (
            f"Stores: {len(self.module.stores)} | "
            f"Keywords: {len(self.module.keywords)} | "
            f"Proxies: {self.module.services.proxy.count}"
        )
        self.status_bar.set_info(info)

    def _update_stats(self) -> None:
        """Update statistics display."""
        tracker_stats = self.module.tracker.get_stats()
        proxy_stats = self.module.services.proxy.get_stats()

        stats_text = (
            f"Stores configured: {len(self.module.stores)}\n"
            f"Keywords configured: {len(self.module.keywords)}\n"
            f"Tracked stores: {tracker_stats['stores']}\n"
            f"Tracked products: {tracker_stats['products']}\n"
            f"Tracked variants: {tracker_stats['variants']}\n"
            f"Proxies: {proxy_stats['total']} total, {proxy_stats['available']} available"
        )
        self.stats_label.config(text=stats_text)

    def _clear_tracker(self) -> None:
        """Clear all tracked products."""
        if messagebox.askyesno("Clear Tracker", "Clear all tracked products?\n\nThis will cause all matching products to be re-notified."):
            self.module.tracker.clear()
            self.module.tracker.save()
            self._update_stats()
            self.module.log("Cleared tracked products")

    def _reload_proxies(self) -> None:
        """Reload proxies from file."""
        count = self.module.services.reload_proxies()
        self._update_info()
        self._update_stats()
        messagebox.showinfo("Reloaded", f"Loaded {count} proxies.")
