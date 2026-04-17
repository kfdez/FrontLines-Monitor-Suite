"""Proxies tab for managing proxies."""
import tkinter as tk
from tkinter import ttk, messagebox


class ProxiesTab(ttk.Frame):
    """Tab for managing proxies."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.colors = getattr(app, "colors", {
            "text": "#eef4ff",
            "text_muted": "#6f83a5",
            "input_bg": "#0f1727",
            "accent_teal": "#35d3b6",
            "accent_blue": "#46b8ff",
            "button_fg": "#08111f",
        })
        self._create_ui()
        self._load_proxies()

    def _create_ui(self):
        """Create the proxies tab UI."""
        # Instructions
        info_frame = ttk.Frame(self, padding=10)
        info_frame.pack(fill=tk.X)

        ttk.Label(
            info_frame,
            text="Enter proxies (one per line) in the format: host:port:username:password",
            wraplength=600
        ).pack(anchor="w")

        # Proxies text area
        text_frame = ttk.Frame(self, padding=10)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.proxies_text = tk.Text(
            text_frame,
            height=20,
            width=60,
            font=("Consolas", 10),
            bg=self.colors["input_bg"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            selectbackground=self.colors["accent_blue"],
            selectforeground=self.colors["button_fg"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=14,
            pady=14
        )
        self.proxies_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, command=self.proxies_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.proxies_text.config(yscrollcommand=scrollbar.set)

        # Buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Save Proxies", command=self._save_proxies).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear", command=self._clear_proxies).pack(side=tk.LEFT, padx=5)

        # Status
        self.status_label = ttk.Label(btn_frame, text="", foreground=self.colors["text_muted"])
        self.status_label.pack(side=tk.LEFT, padx=20)

    def _load_proxies(self):
        """Load proxies from database."""
        proxies = self.app.db.get_config("proxies", "")
        self.proxies_text.delete("1.0", tk.END)
        self.proxies_text.insert("1.0", proxies)
        self._update_status()

    def _save_proxies(self):
        """Save proxies to database."""
        proxies = self.proxies_text.get("1.0", tk.END).strip()
        self.app.db.set_config("proxies", proxies)
        self._update_status()
        messagebox.showinfo("Saved", "Proxies saved successfully.")

    def _clear_proxies(self):
        """Clear the proxies text area."""
        self.proxies_text.delete("1.0", tk.END)

    def _update_status(self):
        """Update status label with proxy count."""
        proxies = self.proxies_text.get("1.0", tk.END).strip()
        if proxies:
            count = len([p for p in proxies.split('\n') if p.strip()])
            self.status_label.config(text=f"{count} proxy(ies) loaded", foreground=self.colors["accent_teal"])
        else:
            self.status_label.config(text="No proxies", foreground=self.colors["text_muted"])

    def get_proxies(self):
        """Get list of proxies from database.

        Returns:
            List of proxy dicts in requests format: [{'http': 'http://user:pass@host:port', 'https': ...}, ...]
        """
        proxies_config = self.app.db.get_config("proxies", "")
        if not proxies_config:
            return []

        proxies_list = []
        for line in proxies_config.strip().split('\n'):
            line = line.strip()
            if not line:
                continue

            # Format: host:port:username:password
            parts = line.split(':')
            if len(parts) >= 4:
                host = parts[0]
                port = parts[1]
                username = parts[2]
                password = ':'.join(parts[3:])  # Password might contain colons

                proxy_url = f"http://{username}:{password}@{host}:{port}"
                proxies_list.append({
                    'http': proxy_url,
                    'https': proxy_url
                })

        return proxies_list

    def get_random_proxy(self):
        """Get a random proxy from the list.

        Returns:
            Proxy dict or None if no proxies
        """
        proxies = self.get_proxies()
        if not proxies:
            return None
        import random
        return random.choice(proxies)
