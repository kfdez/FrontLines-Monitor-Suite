"""Settings tab for bot configuration."""
import tkinter as tk
from tkinter import ttk, messagebox


class SettingsTab(ttk.Frame):
    """Tab for application settings."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._create_ui()
        self._load_settings()

    def _create_ui(self):
        """Create the settings tab UI."""
        # Bot Configuration Section
        config_frame = ttk.LabelFrame(self, text="Bot Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=10)

        # Bot Token
        ttk.Label(config_frame, text="Bot Token:").grid(
            row=0, column=0, sticky='w', pady=5)
        self.token_var = tk.StringVar()
        self.token_entry = ttk.Entry(
            config_frame,
            textvariable=self.token_var,
            width=50,
            show="*"
        )
        self.token_entry.grid(row=0, column=1, pady=5, padx=5)

        # Source Channel ID
        ttk.Label(config_frame, text="Source Channel ID:").grid(
            row=1, column=0, sticky='w', pady=5)
        self.source_channel_var = tk.StringVar()
        ttk.Entry(
            config_frame,
            textvariable=self.source_channel_var,
            width=50
        ).grid(row=1, column=1, pady=5, padx=5)

        # Target Channel ID
        ttk.Label(config_frame, text="Target Channel ID:").grid(
            row=2, column=0, sticky='w', pady=5)
        self.target_channel_var = tk.StringVar()
        ttk.Entry(
            config_frame,
            textvariable=self.target_channel_var,
            width=50
        ).grid(row=2, column=1, pady=5, padx=5)

        # Checkouts Channel ID
        ttk.Label(config_frame, text="Checkouts Channel ID:").grid(
            row=3, column=0, sticky='w', pady=5)
        self.checkouts_channel_var = tk.StringVar()
        ttk.Entry(
            config_frame,
            textvariable=self.checkouts_channel_var,
            width=50
        ).grid(row=3, column=1, pady=5, padx=5)

        # Admin Channel ID
        ttk.Label(config_frame, text="Admin Channel ID:").grid(
            row=4, column=0, sticky='w', pady=5)
        self.admin_channel_var = tk.StringVar()
        ttk.Entry(
            config_frame,
            textvariable=self.admin_channel_var,
            width=50
        ).grid(row=4, column=1, pady=5, padx=5)

        # Enable Ping Checkbox
        self.enable_ping_var = tk.BooleanVar()
        ttk.Checkbutton(
            config_frame,
            text="Enable role ping on forwarded embeds",
            variable=self.enable_ping_var
        ).grid(row=5, column=1, sticky='w', pady=5)

        # Footer Icon URL
        ttk.Label(config_frame, text="Footer Icon URL:").grid(
            row=6, column=0, sticky='w', pady=5)
        self.footer_icon_var = tk.StringVar()
        ttk.Entry(
            config_frame,
            textvariable=self.footer_icon_var,
            width=50
        ).grid(row=6, column=1, pady=5, padx=5)

        # Application Settings Section
        app_frame = ttk.LabelFrame(self, text="Application Settings", padding=10)
        app_frame.pack(fill=tk.X, padx=10, pady=10)

        # Auto-start checkbox
        self.auto_start_var = tk.BooleanVar()
        ttk.Checkbutton(
            app_frame,
            text="Start bot automatically on application launch",
            variable=self.auto_start_var,
            command=self.save_auto_start
        ).pack(anchor='w', pady=5)

        # Save/Load buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(
            btn_frame,
            text="Save Configuration",
            command=self.save_config
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Load Configuration",
            command=self.load_config
        ).pack(side=tk.LEFT, padx=5)

        # Status
        self.status_label = ttk.Label(
            btn_frame,
            text="",
            foreground="green"
        )
        self.status_label.pack(side=tk.LEFT, padx=20)

    def _load_settings(self):
        """Load settings from database."""
        self.token_var.set(self.app.db.get_config("bot_token", ""))
        self.source_channel_var.set(self.app.db.get_config("source_channel_id", ""))
        self.target_channel_var.set(self.app.db.get_config("target_channel_id", ""))
        self.checkouts_channel_var.set(self.app.db.get_config("checkouts_channel_id", ""))
        self.admin_channel_var.set(self.app.db.get_config("admin_channel_id", ""))
        self.enable_ping_var.set(self.app.db.get_config("enable_ping", "false").lower() == "true")
        self.footer_icon_var.set(self.app.db.get_config("footer_icon_url", ""))
        self.auto_start_var.set(self.app.auto_start)

    def save_config(self):
        """Save configuration to database."""
        self.app.db.set_config("bot_token", self.token_var.get().strip())
        self.app.db.set_config("source_channel_id", self.source_channel_var.get().strip())
        self.app.db.set_config("target_channel_id", self.target_channel_var.get().strip())
        self.app.db.set_config("checkouts_channel_id", self.checkouts_channel_var.get().strip())
        self.app.db.set_config("admin_channel_id", self.admin_channel_var.get().strip())
        self.app.db.set_config("enable_ping", "true" if self.enable_ping_var.get() else "false")
        self.app.db.set_config("footer_icon_url", self.footer_icon_var.get().strip())

        # Update bot config
        self.app.bot.token = self.token_var.get().strip()
        self.app.bot.source_channel_id = self._str_to_int(self.source_channel_var.get())
        self.app.bot.target_channel_id = self._str_to_int(self.target_channel_var.get())
        self.app.bot.checkouts_channel_id = self._str_to_int(self.checkouts_channel_var.get())
        self.app.bot.admin_channel_id = self._str_to_int(self.admin_channel_var.get())
        self.app.bot.enable_ping = self.enable_ping_var.get()

        self.status_label.config(text="Configuration saved!")
        self.winfo_toplevel().after(2000, lambda: self.status_label.config(text=""))

    def load_config(self):
        """Reload configuration from database."""
        self._load_settings()
        self.status_label.config(text="Configuration loaded!")
        self.winfo_toplevel().after(2000, lambda: self.status_label.config(text=""))

    def save_auto_start(self):
        """Save auto-start setting."""
        value = "true" if self.auto_start_var.get() else "false"
        self.app.db.set_config("auto_start", value)
        self.app.auto_start = self.auto_start_var.get()

    def _str_to_int(self, value: str):
        """Convert string to int safely."""
        try:
            return int(value) if value else None
        except (ValueError, TypeError):
            return None
