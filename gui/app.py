"""Main GUI application - FrontLines Monitor Suite."""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
from datetime import datetime
import discord

# Add parent directory to path for imports
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import Database
from core.sheets import SheetsManager
from core.bot import DiscordBot
from core.hv_monitor import HVMonitor
from core.shopify_monitor import ShopifyMonitor
from core.tasks import TasksManager
from gui.tabs.products_tab import ProductsTab
from gui.tabs.emails_tab import EmailsTab
from gui.tabs.settings_tab import SettingsTab
from gui.tabs.hv_monitor_tab import HVMonitorTab
from gui.tabs.shopify_monitor_tab import ShopifyMonitorTab
from gui.tabs.proxies_tab import ProxiesTab

APP_COLORS = {
    "bg": "#0b1220",
    "panel": "#121b2d",
    "panel_alt": "#182338",
    "panel_soft": "#21314a",
    "panel_hover": "#243652",
    "border": "#2a3c5b",
    "text": "#eef4ff",
    "text_secondary": "#a9b8d0",
    "text_muted": "#6f83a5",
    "accent_blue": "#46b8ff",
    "accent_teal": "#35d3b6",
    "accent_gold": "#ffb84d",
    "success": "#33d17a",
    "danger": "#ff6b81",
    "warning": "#ffb84d",
    "disabled": "#4b5e80",
    "terminal": "#0a101b",
    "input_bg": "#0f1727",
    "button_fg": "#08111f",
}

VIEW_META = {
    "skutto": ("SKUtto", "Discord restock routing, embed transforms, and operator controls."),
    "shopify": ("Shopify Monitor", "Multi-store scanning, keyword filters, and webhook delivery."),
    "hobbiesville": ("Hobbiesville", "Single-store GraphQL monitoring for tracked product and variant IDs."),
    "proxies": ("Proxies", "Shared proxy pool used by the monitoring modules."),
}


class ColoredButton(ttk.Button):
    """Custom styled button."""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(style="Custom.TButton")


class LogPanel(tk.Frame):
    """Scrolling log panel for bot events."""

    MAX_LINES = 1000  # Maximum lines to keep in log

    def __init__(self, parent, title: str = "Activity Stream"):
        super().__init__(
            parent,
            bg=APP_COLORS["panel_alt"],
            highlightthickness=1,
            highlightbackground=APP_COLORS["border"]
        )
        self.title = title
        self._create_ui()

    def _create_ui(self):
        """Create the log panel UI."""
        # Header
        header_frame = tk.Frame(self, bg=APP_COLORS["panel_alt"])
        header_frame.pack(fill=tk.X, padx=16, pady=(14, 6))

        title_block = tk.Frame(header_frame, bg=APP_COLORS["panel_alt"])
        title_block.pack(side=tk.LEFT)
        tk.Label(
            title_block,
            text=self.title,
            font=("Bahnschrift SemiBold", 12),
            bg=APP_COLORS["panel_alt"],
            fg=APP_COLORS["text"]
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text="Timestamped operational events",
            font=("Segoe UI", 9),
            bg=APP_COLORS["panel_alt"],
            fg=APP_COLORS["text_muted"]
        ).pack(anchor="w")

        clear_btn = ttk.Button(header_frame, text="Clear", command=self.clear_log, width=8, style="Secondary.TButton")
        clear_btn.pack(side=tk.RIGHT)

        # Log text area with styling
        self.log_text = tk.Text(
            self,
            height=9,
            font=("Consolas", 9),
            bg=APP_COLORS["terminal"],
            fg=APP_COLORS["text_secondary"],
            insertbackground=APP_COLORS["text"],
            relief=tk.FLAT,
            wrap=tk.WORD,
            padx=14,
            pady=12,
            selectbackground=APP_COLORS["accent_blue"],
            selectforeground=APP_COLORS["button_fg"],
            borderwidth=0,
            highlightthickness=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=(16, 0), pady=(0, 16), side=tk.LEFT)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 16), pady=(0, 16))
        self.log_text.config(yscrollcommand=scrollbar.set)

    def add_log(self, message: str):
        """Add a timestamped message to the log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

        # Trim old lines if over limit
        line_count = int(self.log_text.index("end-1c").split('.')[0])
        if line_count > self.MAX_LINES:
            lines_to_delete = line_count - self.MAX_LINES
            self.log_text.delete("1.0", f"{lines_to_delete + 1}.0")

    def clear_log(self):
        """Clear the log."""
        self.log_text.delete(1.0, tk.END)


class MainApplication:
    """Main application window - FrontLines Monitor Suite."""

    def __init__(self, root):
        self.root = root
        self.root.title("FrontLines Monitor Suite")
        self.colors = APP_COLORS
        self.view_meta = VIEW_META
        self.root.configure(bg=self.colors["bg"])
        self.root.option_add("*Font", "Bahnschrift 10")
        self.root.option_add("*TCombobox*Listbox.font", "Bahnschrift 10")
        self.root.option_add("*Text.background", self.colors["input_bg"])
        self.root.option_add("*Text.foreground", self.colors["text"])
        self.root.option_add("*Text.insertBackground", self.colors["text"])
        self.root.option_add("*Canvas.background", self.colors["bg"])

        # Center window on screen manually
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 1200
        window_height = 950
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.root.minsize(1000, 700)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Set window and taskbar icon using ICO file
        ico_path = "app.ico"
        try:
            self.root.iconbitmap(ico_path)
        except Exception:
            pass

        # Setup system tray
        self._setup_system_tray()

        # Configure custom styles
        self._configure_styles()

        # Initialize core components
        self.db = Database()
        self.sheets = SheetsManager()
        self.bot = DiscordBot("", self.db)
        self.hv_monitor = HVMonitor(self.db, log_callback=None, app=self)
        self.shopify_monitor = ShopifyMonitor(self.db, log_callback=None, app=self)
        self.tasks_manager = TasksManager(self.db, log_callback=self.log_message)

        # Bot state
        self.bot_thread = None

        # Duplicate forwarding prevention
        self.recent_forwards = {}  # SKU -> timestamp

        # Load saved config
        self._load_config()

        # Create main UI
        self._create_ui()

        # Defer heavy operations to let UI render first
        self.root.after(100, self._delayed_init)

    def _set_taskbar_icon(self):
        """Set the taskbar icon after window is displayed."""
        # Use ICO file for proper Windows taskbar support
        ico_path = "app.ico"
        try:
            self.root.iconbitmap(ico_path)
        except Exception:
            pass

    def _delayed_init(self):
        """Perform heavy initialization after UI is shown."""
        # Set taskbar icon after window is fully displayed
        self.root.after_idle(self._set_taskbar_icon)

        # Initialize tasks manager (can be slow with large files)
        self.bot.set_tasks_manager(self.tasks_manager)
        self.tasks_manager.load_tasks()
        self.tasks_manager.start_auto_refresh()

        # Auto-start bot if enabled (deferred)
        if self.auto_start:
            self.root.after(500, self.start_bot)

        # Auto-start HV monitor if enabled (deferred)
        if self.hv_monitor.auto_start:
            self.root.after(600, self.start_hv_monitor)

        # Auto-start Shopify monitor if enabled (deferred)
        if self.shopify_monitor.auto_start:
            self.root.after(700, self.start_shopify_monitor)

    def _configure_styles(self):
        """Configure custom styles."""
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=self.colors["bg"], foreground=self.colors["text"], font=("Bahnschrift", 10))
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("Card.TFrame", background=self.colors["panel_alt"])
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"])
        style.configure("Muted.TLabel", background=self.colors["bg"], foreground=self.colors["text_muted"], font=("Segoe UI", 9))
        style.configure("Section.TLabel", background=self.colors["bg"], foreground=self.colors["text_secondary"], font=("Bahnschrift SemiBold", 9))

        style.configure(
            "TLabelframe",
            background=self.colors["panel_alt"],
            bordercolor=self.colors["border"],
            relief=tk.FLAT,
            borderwidth=1,
            padding=16
        )
        style.configure(
            "TLabelframe.Label",
            background=self.colors["panel_alt"],
            foreground=self.colors["text"],
            font=("Bahnschrift SemiBold", 11)
        )

        style.configure(
            "Custom.TButton",
            padding=(16, 10),
            font=("Bahnschrift SemiBold", 10),
            background=self.colors["panel_soft"],
            foreground=self.colors["text"],
            borderwidth=0
        )
        style.configure("Secondary.TButton", padding=(14, 9), font=("Bahnschrift SemiBold", 10), background=self.colors["panel_soft"], foreground=self.colors["text"], borderwidth=0)
        style.map(
            "Secondary.TButton",
            background=[("active", self.colors["panel_hover"]), ("disabled", self.colors["disabled"])],
            foreground=[("disabled", self.colors["text_muted"])]
        )
        style.configure("Success.TButton", padding=(16, 10), font=("Bahnschrift SemiBold", 10), background=self.colors["success"], foreground=self.colors["button_fg"], borderwidth=0)
        style.configure("Danger.TButton", padding=(16, 10), font=("Bahnschrift SemiBold", 10), background=self.colors["danger"], foreground=self.colors["button_fg"], borderwidth=0)

        style.configure(
            "TEntry",
            fieldbackground=self.colors["input_bg"],
            foreground=self.colors["text"],
            insertcolor=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            padding=8
        )
        style.configure(
            "TSpinbox",
            fieldbackground=self.colors["input_bg"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            arrowsize=14,
            padding=6
        )
        style.configure(
            "TCombobox",
            fieldbackground=self.colors["input_bg"],
            background=self.colors["input_bg"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            arrowcolor=self.colors["text_secondary"],
            padding=6
        )
        style.map("TCombobox", fieldbackground=[("readonly", self.colors["input_bg"])])

        style.configure(
            "Treeview",
            background=self.colors["panel_alt"],
            fieldbackground=self.colors["panel_alt"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            rowheight=34,
            relief=tk.FLAT
        )
        style.configure(
            "Treeview.Heading",
            background=self.colors["panel_soft"],
            foreground=self.colors["text"],
            font=("Bahnschrift SemiBold", 10),
            borderwidth=0,
            padding=(10, 10)
        )
        style.map(
            "Treeview",
            background=[("selected", self.colors["accent_blue"])],
            foreground=[("selected", self.colors["button_fg"])]
        )
        style.map("Treeview.Heading", background=[("active", self.colors["panel_hover"])])

        style.configure("TNotebook", background=self.colors["bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=self.colors["panel"],
            foreground=self.colors["text_secondary"],
            padding=(18, 10),
            font=("Bahnschrift SemiBold", 10),
            borderwidth=0
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.colors["panel_alt"]), ("active", self.colors["panel_hover"])],
            foreground=[("selected", self.colors["text"]), ("active", self.colors["text"])]
        )

        style.configure(
            "TCheckbutton",
            background=self.colors["panel_alt"],
            foreground=self.colors["text"],
            indicatorcolor=self.colors["input_bg"],
            padding=4
        )
        style.map("TCheckbutton", background=[("active", self.colors["panel_alt"])])

        style.configure(
            "TScrollbar",
            background=self.colors["panel_soft"],
            troughcolor=self.colors["bg"],
            arrowcolor=self.colors["text_secondary"],
            bordercolor=self.colors["bg"],
            darkcolor=self.colors["panel_soft"],
            lightcolor=self.colors["panel_soft"]
        )
        style.configure(
            "Horizontal.TProgressbar",
            background=self.colors["accent_blue"],
            troughcolor=self.colors["panel"],
            bordercolor=self.colors["panel"]
        )

    def _create_flat_button(self, parent, text: str, command, role: str = "secondary", width: int = 12):
        """Create a flat, modern tk.Button."""
        bg_map = {
            "success": self.colors["success"],
            "danger": self.colors["danger"],
            "secondary": self.colors["panel_soft"],
            "ghost": self.colors["panel"],
        }
        hover_map = {
            "success": "#4de08e",
            "danger": "#ff8093",
            "secondary": self.colors["panel_hover"],
            "ghost": self.colors["panel_hover"],
        }
        button = tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
            font=("Bahnschrift SemiBold", 10),
            bg=bg_map[role],
            fg=self.colors["button_fg"] if role in {"success", "danger"} else self.colors["text"],
            activebackground=hover_map[role],
            activeforeground=self.colors["button_fg"] if role in {"success", "danger"} else self.colors["text"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            padx=14,
            pady=9,
            disabledforeground=self.colors["text_muted"],
        )
        button._role = role
        button._bg_map = bg_map
        button._hover_map = hover_map
        return button

    def _set_action_button_state(self, button: tk.Button, enabled: bool):
        """Update header button visuals for enabled/disabled states."""
        role = getattr(button, "_role", "secondary")
        bg_map = getattr(button, "_bg_map", {})
        hover_map = getattr(button, "_hover_map", {})
        if enabled:
            button.config(
                state=tk.NORMAL,
                bg=bg_map.get(role, self.colors["panel_soft"]),
                fg=self.colors["button_fg"] if role in {"success", "danger"} else self.colors["text"],
                activebackground=hover_map.get(role, self.colors["panel_hover"]),
                activeforeground=self.colors["button_fg"] if role in {"success", "danger"} else self.colors["text"],
            )
        else:
            button.config(
                state=tk.DISABLED,
                bg=self.colors["disabled"],
                fg=self.colors["text_muted"],
                activebackground=self.colors["disabled"],
                activeforeground=self.colors["text_muted"],
            )

    def _set_status_badge(self, badge: tk.Frame, indicator: tk.Canvas, circle: int, label: tk.Label, state_key: str, text: str):
        """Apply consistent colors to a module status badge."""
        badge_colors = {
            "offline": ("#321f2a", self.colors["danger"]),
            "running": ("#16392d", self.colors["success"]),
            "starting": ("#43351d", self.colors["warning"]),
        }
        badge_bg, fg = badge_colors.get(state_key, badge_colors["offline"])
        badge.config(bg=badge_bg)
        indicator.config(bg=badge_bg)
        indicator.itemconfig(circle, fill=fg)
        label.config(text=text, bg=badge_bg, fg=fg)

    def _create_module_header(
        self,
        parent,
        title: str,
        subtitle: str,
        accent: str,
        start_command=None,
        stop_command=None,
        include_loading: bool = False
    ):
        """Create a shared modern header card for each module."""
        header_card = tk.Frame(
            parent,
            bg=self.colors["panel_alt"],
            highlightthickness=1,
            highlightbackground=self.colors["border"]
        )
        header_card.pack(fill=tk.X, pady=(0, 18))

        accent_strip = tk.Frame(header_card, bg=accent, width=6)
        accent_strip.pack(side=tk.LEFT, fill=tk.Y)

        content = tk.Frame(header_card, bg=self.colors["panel_alt"])
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=18, pady=18)

        left_block = tk.Frame(content, bg=self.colors["panel_alt"])
        left_block.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            left_block,
            text="CONTROL SURFACE",
            font=("Bahnschrift SemiBold", 9),
            bg=self.colors["panel_alt"],
            fg=self.colors["text_muted"]
        ).pack(anchor="w")
        tk.Label(
            left_block,
            text=title,
            font=("Bahnschrift SemiBold", 24),
            bg=self.colors["panel_alt"],
            fg=self.colors["text"]
        ).pack(anchor="w", pady=(4, 4))
        tk.Label(
            left_block,
            text=subtitle,
            font=("Segoe UI", 10),
            bg=self.colors["panel_alt"],
            fg=self.colors["text_secondary"],
            wraplength=640,
            justify=tk.LEFT
        ).pack(anchor="w")

        status_row = tk.Frame(left_block, bg=self.colors["panel_alt"])
        status_row.pack(anchor="w", pady=(14, 0))
        status_badge = tk.Frame(status_row, bg="#321f2a", padx=10, pady=6)
        status_badge.pack(side=tk.LEFT)
        status_indicator = tk.Canvas(status_badge, width=12, height=12, bg="#321f2a", highlightthickness=0)
        status_indicator.pack(side=tk.LEFT, padx=(0, 8))
        status_circle = status_indicator.create_oval(2, 2, 10, 10, fill=self.colors["danger"], outline="")
        status_label = tk.Label(
            status_badge,
            text="Offline",
            font=("Bahnschrift SemiBold", 10),
            bg="#321f2a",
            fg=self.colors["danger"]
        )
        status_label.pack(side=tk.LEFT)

        loading_frame = None
        loading_bar = None
        if include_loading:
            loading_frame = tk.Frame(left_block, bg=self.colors["panel_alt"])
            loading_bar = ttk.Progressbar(
                loading_frame,
                mode="indeterminate",
                length=90,
                style="Horizontal.TProgressbar",
                takefocus=False
            )
            loading_bar.pack(anchor="w", pady=(10, 0))

        right_block = tk.Frame(content, bg=self.colors["panel_alt"])
        right_block.pack(side=tk.RIGHT, anchor="n", padx=(20, 0))
        actions = tk.Frame(right_block, bg=self.colors["panel_alt"])
        actions.pack(anchor="e")

        start_btn = stop_btn = None
        if start_command:
            start_btn = self._create_flat_button(actions, "Start", start_command, role="success")
            start_btn.pack(side=tk.LEFT, padx=(0, 8))
        if stop_command:
            stop_btn = self._create_flat_button(actions, "Stop", stop_command, role="danger")
            stop_btn.pack(side=tk.LEFT)
            self._set_action_button_state(stop_btn, False)

        return {
            "status_badge": status_badge,
            "status_indicator": status_indicator,
            "status_circle": status_circle,
            "status_label": status_label,
            "loading_frame": loading_frame,
            "loading_bar": loading_bar,
            "start_btn": start_btn,
            "stop_btn": stop_btn,
        }

    def _get_nav_text(self, view_id: str) -> str:
        """Render the current sidebar label for a view."""
        btn_data = self.nav_buttons[view_id]
        if not self.sidebar_expanded:
            return btn_data["collapsed"]
        if not btn_data.get("has_indicator", True):
            return btn_data["expanded"]
        indicator = "●" if self._module_status.get(view_id) else "○"
        return f"{indicator}  {btn_data['expanded']}"

    def _apply_nav_styles(self, active_view: str = None):
        """Apply sidebar navigation visuals."""
        active_view = active_view or getattr(self, "current_view", None)
        for btn_id, btn_data in self.nav_buttons.items():
            is_active = btn_id == active_view
            is_running = self._module_status.get(btn_id, False)
            fg = self.colors["text"]
            if not is_active and btn_data.get("has_indicator", True):
                fg = self.colors["success"] if is_running else self.colors["text_secondary"]
            elif not is_active:
                fg = self.colors["text_secondary"]

            btn_data["btn"].config(
                text=self._get_nav_text(btn_id),
                bg=self.colors["panel_soft"] if is_active else self.colors["panel"],
                fg=fg,
                activebackground=self.colors["panel_hover"],
                activeforeground=self.colors["text"],
                anchor="w" if self.sidebar_expanded else tk.CENTER,
                justify=tk.LEFT if self.sidebar_expanded else tk.CENTER,
                padx=18 if self.sidebar_expanded else 8,
            )

    def _load_config(self):
        """Load configuration from database."""
        self.bot.token = self.db.get_config("bot_token", "")
        self.bot.source_channel_id = self._str_to_int(
            self.db.get_config("source_channel_id", ""))
        self.bot.target_channel_id = self._str_to_int(
            self.db.get_config("target_channel_id", ""))
        self.bot.checkouts_channel_id = self._str_to_int(
            self.db.get_config("checkouts_channel_id", ""))
        self.bot.checkouts_target_channel_id = self._str_to_int(
            self.db.get_config("checkouts_target_channel_id", ""))
        self.bot.admin_channel_id = self._str_to_int(
            self.db.get_config("admin_channel_id", ""))
        self.bot.enable_ping = self.db.get_config("enable_ping", "false").lower() == "true"

        # Auto-start setting
        self.auto_start = self.db.get_config("auto_start", "false").lower() == "true"

        # Duplicate timeout (in seconds)
        self.duplicate_timeout = int(self.db.get_config("duplicate_timeout", "60"))

        # Debug logging toggle
        self.debug_logging = self.db.get_config("debug_logging", "false").lower() == "true"

    @property
    def proxies(self) -> list:
        """Get list of proxies from database."""
        proxies_config = self.db.get_config("proxies", "")
        if not proxies_config:
            return []
        proxies_list = []
        for line in proxies_config.strip().split('\n'):
            line = line.strip()
            if line and ':' in line:
                proxies_list.append(line)
        return proxies_list

    def _str_to_int(self, value: str) -> int:
        """Convert string to int safely."""
        try:
            return int(value) if value else None
        except (ValueError, TypeError):
            return None

    def log_message(self, message: str):
        """Add a message to the log panel."""
        if hasattr(self, 'log_panel') and self.log_panel is not None:
            self.root.after(0, self._add_log_to_panel, message)

    def _add_log_to_panel(self, message: str):
        """Actually add the log message to the panel (called on main thread)."""
        if hasattr(self, 'log_panel') and self.log_panel is not None:
            self.log_panel.add_log(message)

    def _update_nav_indicator(self, module: str, running: bool):
        """Update the sidebar indicator for a module."""
        self._module_status[module] = running
        self._apply_nav_styles(getattr(self, "current_view", None))

    def _create_ui(self):
        """Create the main UI."""
        main_container = tk.Frame(self.root, bg=self.colors["bg"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        self.sidebar_frame = tk.Frame(
            main_container,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["border"]
        )
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 18))
        self.sidebar_frame.config(width=240)
        self.sidebar_expanded = True
        self.sidebar_width = 240

        self.sidebar_brand = tk.Frame(
            self.sidebar_frame,
            bg=self.colors["panel_alt"],
            highlightthickness=1,
            highlightbackground=self.colors["border"]
        )
        self.sidebar_brand.pack(fill=tk.X, padx=14, pady=(14, 12))
        self.sidebar_title = tk.Label(
            self.sidebar_brand,
            text="FrontLines\nMonitor Suite",
            font=("Bahnschrift SemiBold", 18),
            bg=self.colors["panel_alt"],
            fg=self.colors["text"],
            pady=16,
            padx=16,
            justify=tk.LEFT,
            anchor="w"
        )
        self.sidebar_title.pack(fill=tk.X)
        self.sidebar_subtitle = tk.Label(
            self.sidebar_brand,
            text="Control room for Discord relays, Shopify scans, and operator tooling.",
            font=("Segoe UI", 9),
            bg=self.colors["panel_alt"],
            fg=self.colors["text_muted"],
            padx=16,
            pady=(0, 14),
            justify=tk.LEFT,
            wraplength=180
        )
        self.sidebar_subtitle.pack(fill=tk.X)

        self.sidebar_section = tk.Label(
            self.sidebar_frame,
            text="MODULES",
            font=("Bahnschrift SemiBold", 9),
            bg=self.colors["panel"],
            fg=self.colors["text_muted"],
            padx=18,
            pady=4,
            anchor="w"
        )
        self.sidebar_section.pack(fill=tk.X)

        self.nav_button_container = tk.Frame(self.sidebar_frame, bg=self.colors["panel"])
        self.nav_button_container.pack(fill=tk.X, padx=10, pady=(0, 14))

        self.minimize_to_tray_var = tk.BooleanVar(value=False)
        self.minimize_to_tray_checkbox = tk.Checkbutton(
            self.sidebar_frame,
            text="Minimize to tray",
            variable=self.minimize_to_tray_var,
            bg=self.colors["panel"],
            fg=self.colors["text_secondary"],
            selectcolor=self.colors["panel"],
            activebackground=self.colors["panel"],
            activeforeground=self.colors["text"],
            highlightthickness=0,
            bd=0,
            padx=18,
            pady=6,
            anchor="w",
            justify=tk.LEFT
        )
        self.minimize_to_tray_checkbox.pack(fill=tk.X, pady=(0, 10))
        self._load_minimize_to_tray_setting()

        self.sidebar_footer = tk.Label(
            self.sidebar_frame,
            text="Operator view",
            font=("Segoe UI", 9),
            bg=self.colors["panel"],
            fg=self.colors["text_muted"],
            padx=18,
            pady=8,
            anchor="w"
        )
        self.sidebar_footer.pack(side=tk.BOTTOM, fill=tk.X)

        self.collapse_btn = tk.Button(
            self.sidebar_frame,
            text="◀",
            font=("Bahnschrift SemiBold", 10),
            bg=self.colors["panel_soft"],
            fg=self.colors["text"],
            relief=tk.FLAT,
            padx=10,
            pady=8,
            cursor="hand2",
            command=self._toggle_sidebar,
            activebackground=self.colors["panel_hover"],
            activeforeground=self.colors["text"],
            highlightthickness=0,
            bd=0
        )
        self.collapse_btn.pack(side=tk.BOTTOM, padx=14, pady=(0, 12), fill=tk.X)

        self.nav_buttons = {}
        views = [
            ("skutto", "SKUtto", "[S]"),
            ("shopify", "Shopify Monitor", "[$]"),
            ("hobbiesville", "Hobbiesville", "[H]"),
            ("proxies", "Proxy Pool", "[P]"),
        ]

        for view_id, expanded_text, collapsed_text in views:
            btn = tk.Button(
                self.nav_button_container,
                text=expanded_text,
                font=("Bahnschrift SemiBold", 11),
                bg=self.colors["panel"],
                fg=self.colors["text_secondary"],
                relief=tk.FLAT,
                anchor="w",
                padx=18,
                pady=12,
                cursor="hand2",
                command=lambda v=view_id: self._switch_view(v),
                activebackground=self.colors["panel_hover"],
                activeforeground=self.colors["text"],
                highlightthickness=0,
                bd=0
            )
            btn.pack(fill=tk.X, pady=4)
            self.nav_buttons[view_id] = {
                'btn': btn,
                'expanded': expanded_text,
                'collapsed': collapsed_text,
                'has_indicator': view_id != "proxies"
            }

        self._module_status = {
            'skutto': False,
            'hobbiesville': False,
            'shopify': False
        }

        content_container = tk.Frame(main_container, bg=self.colors["bg"])
        content_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.app_bar = tk.Frame(content_container, bg=self.colors["bg"])
        self.app_bar.pack(fill=tk.X, pady=(0, 14))
        left_bar = tk.Frame(self.app_bar, bg=self.colors["bg"])
        left_bar.pack(side=tk.LEFT)
        tk.Label(
            left_bar,
            text="COMMAND DESK",
            font=("Bahnschrift SemiBold", 9),
            bg=self.colors["bg"],
            fg=self.colors["text_muted"]
        ).pack(anchor="w")
        self.content_title_label = tk.Label(
            left_bar,
            text="SKUtto",
            font=("Bahnschrift SemiBold", 28),
            bg=self.colors["bg"],
            fg=self.colors["text"]
        )
        self.content_title_label.pack(anchor="w")
        self.content_subtitle_label = tk.Label(
            left_bar,
            text="Discord restock routing, embed transforms, and operator controls.",
            font=("Segoe UI", 10),
            bg=self.colors["bg"],
            fg=self.colors["text_secondary"]
        )
        self.content_subtitle_label.pack(anchor="w")

        right_bar = tk.Frame(self.app_bar, bg=self.colors["bg"])
        right_bar.pack(side=tk.RIGHT, anchor="n")
        tk.Label(
            right_bar,
            text="FrontLines 3.0",
            font=("Bahnschrift SemiBold", 10),
            bg=self.colors["panel_soft"],
            fg=self.colors["text"],
            padx=12,
            pady=8
        ).pack(anchor="e")

        self.views_container = tk.Frame(content_container, bg=self.colors["bg"])
        self.views_container.pack(fill=tk.BOTH, expand=True)

        self.views = {}
        self.view_log_panels = {}

        self._create_skutto_view(content_container)
        self._create_hv_monitor_view(content_container)
        self._create_shopify_monitor_view(content_container)
        self._create_proxies_view(content_container)

        self._switch_view("skutto")
        self.current_view = "skutto"

    def _toggle_sidebar(self):
        """Toggle the sidebar collapsed/expanded."""
        if self.sidebar_expanded:
            self.sidebar_frame.config(width=86)
            self.sidebar_title.config(text="FLMS", justify=tk.CENTER, anchor="center")
            self.sidebar_subtitle.pack_forget()
            self.sidebar_section.pack_forget()
            self.sidebar_footer.pack_forget()
            self.minimize_to_tray_checkbox.config(text="Tray", padx=10)
            self.collapse_btn.config(text="▶")
            self.sidebar_expanded = False
        else:
            self.sidebar_frame.config(width=self.sidebar_width)
            self.sidebar_title.config(text="FrontLines\nMonitor Suite", justify=tk.LEFT, anchor="w")
            self.sidebar_subtitle.pack(fill=tk.X)
            self.sidebar_section.pack(fill=tk.X, before=self.nav_button_container)
            self.sidebar_footer.pack(side=tk.BOTTOM, fill=tk.X)
            self.minimize_to_tray_checkbox.config(text="Minimize to tray", padx=18)
            self.collapse_btn.config(text="◀")
            self.sidebar_expanded = True
        self._apply_nav_styles(self.current_view)

    def _create_skutto_view(self, parent):
        """Create the SKUtto view with tabs, header controls, and log."""
        skutto_frame = tk.Frame(self.views_container, bg=self.colors["bg"])
        self.views["skutto"] = skutto_frame

        header = self._create_module_header(
            skutto_frame,
            "SKUtto",
            "Monitor Discord restock embeds, clean the payload, and forward matched alerts with role pings.",
            self.colors["accent_blue"],
            start_command=self.start_bot,
            stop_command=self.stop_bot,
            include_loading=True
        )
        self.status_badge = header["status_badge"]
        self.status_indicator = header["status_indicator"]
        self.status_circle = header["status_circle"]
        self.status_label = header["status_label"]
        self.loading_frame = header["loading_frame"]
        self.loading_bar = header["loading_bar"]
        self.start_btn = header["start_btn"]
        self.stop_btn = header["stop_btn"]

        # Create notebook for tabs
        self.notebook = ttk.Notebook(skutto_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.products_tab = ProductsTab(self.notebook, self)
        self.emails_tab = EmailsTab(self.notebook, self)
        self.settings_tab = SettingsTab(self.notebook, self)

        # Add tabs to notebook
        self.notebook.add(self.products_tab, text="Products")
        self.notebook.add(self.emails_tab, text="Emails")
        self.notebook.add(self.settings_tab, text="Settings")

        # Log panel for SKUtto
        self.log_panel = LogPanel(skutto_frame, title="SKUtto Activity")
        self.log_panel.pack(fill=tk.X, pady=(10, 0))

        # Add welcome message
        self.log_panel.add_log("FrontLines Monitor Suite started")
        self.log_panel.add_log("Configure bot settings in the Settings tab")

        # Load data on startup
        self.products_tab.load_products()
        self.products_tab.load_pending()
        self.products_tab.load_platforms()
        self.emails_tab.load_emails()

    def _create_hv_monitor_view(self, parent):
        """Create the Hobbiesville (HV Monitor) view with controls and tabs."""
        hv_frame = tk.Frame(self.views_container, bg=self.colors["bg"])
        self.views["hobbiesville"] = hv_frame

        header = self._create_module_header(
            hv_frame,
            "Hobbiesville Monitor",
            "Track specific Shopify products or variants through the Storefront GraphQL endpoint and push stock changes to Discord.",
            self.colors["accent_teal"],
            start_command=self.start_hv_monitor,
            stop_command=self.stop_hv_monitor
        )
        self.hv_status_badge = header["status_badge"]
        self.hv_status_indicator = header["status_indicator"]
        self.hv_status_circle = header["status_circle"]
        self.hv_status_label = header["status_label"]
        self.hv_start_btn = header["start_btn"]
        self.hv_stop_btn = header["stop_btn"]

        # Create HV Monitor tab
        self.hv_monitor_tab = HVMonitorTab(hv_frame, self)
        self.hv_monitor_tab.pack(fill=tk.BOTH, expand=True)

        # Log panel for HV Monitor
        self.hv_log_panel = LogPanel(hv_frame, title="Hobbiesville Activity")
        self.hv_log_panel.pack(fill=tk.X, pady=(10, 0))
        self.hv_log_panel.add_log("HV Monitor loaded")
        self.hv_log_panel.add_log("Configure settings in the Configuration tab")

        # Set UI refresh callback for hv_monitor
        self.hv_monitor.ui_refresh_callback = self.hv_monitor_tab.refresh_products

        # Set hv_monitor's own log callback to use hv_log_panel
        self.hv_monitor.hv_log_callback = self.hv_log_panel.add_log

    def start_hv_monitor(self):
        """Start the HV Monitor."""
        if not self.hv_monitor.store_url or not self.hv_monitor.token:
            self.hv_log_panel.add_log("Error: Store URL and Token not configured")
            messagebox.showerror("Error", "Please configure Store URL and Token in Configuration tab first.")
            return

        self.hv_monitor.start()
        self._set_status_badge(self.hv_status_badge, self.hv_status_indicator, self.hv_status_circle, self.hv_status_label, "running", "Running")
        self._set_action_button_state(self.hv_start_btn, False)
        self._set_action_button_state(self.hv_stop_btn, True)
        self._update_nav_indicator('hobbiesville', True)
        self.hv_log_panel.add_log("Monitor started")

    def stop_hv_monitor(self):
        """Stop the HV Monitor."""
        self.hv_monitor.stop()
        self._set_status_badge(self.hv_status_badge, self.hv_status_indicator, self.hv_status_circle, self.hv_status_label, "offline", "Offline")
        self._set_action_button_state(self.hv_start_btn, True)
        self._set_action_button_state(self.hv_stop_btn, False)
        self._update_nav_indicator('hobbiesville', False)
        self.hv_log_panel.add_log("Monitor stopped")

    def _create_shopify_monitor_view(self, parent):
        """Create the Shopify Monitor view."""
        shopify_frame = tk.Frame(self.views_container, bg=self.colors["bg"])
        self.views["shopify"] = shopify_frame

        header = self._create_module_header(
            shopify_frame,
            "Shopify Monitor",
            "Run concurrent multi-store scans, filter by keywords, and route main or singles alerts to the correct webhooks.",
            self.colors["accent_gold"],
            start_command=self.start_shopify_monitor,
            stop_command=self.stop_shopify_monitor
        )
        self.shopify_status_badge = header["status_badge"]
        self.shopify_status_indicator = header["status_indicator"]
        self.shopify_status_circle = header["status_circle"]
        self.shopify_status_label = header["status_label"]
        self.shopify_start_btn = header["start_btn"]
        self.shopify_stop_btn = header["stop_btn"]

        # Create Shopify Monitor tab
        self.shopify_monitor_tab = ShopifyMonitorTab(shopify_frame, self)
        self.shopify_monitor_tab.pack(fill=tk.BOTH, expand=True)

        # Log panel for Shopify Monitor
        self.shopify_log_panel = LogPanel(shopify_frame, title="Shopify Monitor Activity")
        self.shopify_log_panel.pack(fill=tk.X, pady=(10, 0))
        self.shopify_log_panel.add_log("Shopify Monitor loaded")
        self.shopify_log_panel.add_log("Configure settings in the Configuration tab")

        # Set shopify_monitor's own log callback to use shopify_log_panel
        self.shopify_monitor.shopify_log_callback = self.shopify_log_panel.add_log

        # Update button states
        self._update_shopify_button_states()

        # Update button states
        self._update_shopify_button_states()

    def start_shopify_monitor(self):
        """Start the Shopify Monitor."""
        if not self.shopify_monitor.stores:
            self.shopify_log_panel.add_log("Error: No stores configured")
            messagebox.showerror("Error", "Please configure at least one store in the Configuration tab.")
            return

        if not self.shopify_monitor.keywords:
            self.shopify_log_panel.add_log("Error: No keywords configured")
            messagebox.showerror("Error", "Please configure at least one keyword in the Configuration tab.")
            return

        self.shopify_monitor.start()
        self._set_status_badge(self.shopify_status_badge, self.shopify_status_indicator, self.shopify_status_circle, self.shopify_status_label, "running", "Running")
        self._set_action_button_state(self.shopify_start_btn, False)
        self._set_action_button_state(self.shopify_stop_btn, True)
        self._update_nav_indicator('shopify', True)
        self.shopify_log_panel.add_log("Monitor started")

    def stop_shopify_monitor(self):
        """Stop the Shopify Monitor."""
        self.shopify_monitor.stop()
        self._set_status_badge(self.shopify_status_badge, self.shopify_status_indicator, self.shopify_status_circle, self.shopify_status_label, "offline", "Offline")
        self._set_action_button_state(self.shopify_start_btn, True)
        self._set_action_button_state(self.shopify_stop_btn, False)
        self._update_nav_indicator('shopify', False)
        self.shopify_log_panel.add_log("Monitor stopped")

    def _update_shopify_button_states(self):
        """Update Shopify Monitor start/stop button states."""
        if self.shopify_monitor._running:
            self._set_action_button_state(self.shopify_start_btn, False)
            self._set_action_button_state(self.shopify_stop_btn, True)
        else:
            self._set_action_button_state(self.shopify_start_btn, True)
            self._set_action_button_state(self.shopify_stop_btn, False)

    def _create_proxies_view(self, parent):
        """Create the Proxies view."""
        proxies_frame = tk.Frame(self.views_container, bg=self.colors["bg"])
        self.views["proxies"] = proxies_frame

        self._create_module_header(
            proxies_frame,
            "Proxy Pool",
            "Edit the shared proxy list used by Hobbiesville and Shopify monitor requests.",
            self.colors["accent_teal"]
        )

        # Create Proxies tab
        self.proxies_tab = ProxiesTab(proxies_frame, self)
        self.proxies_tab.pack(fill=tk.BOTH, expand=True)

    def _create_placeholder_view(self, view_id: str, title: str, message: str, has_log: bool = True):
        """Create a placeholder view."""
        placeholder_frame = tk.Frame(self.views_container, bg=self.colors["bg"])
        self.views[view_id] = placeholder_frame

        self._create_module_header(
            placeholder_frame,
            title,
            message,
            self.colors["accent_blue"]
        )

        center_frame = tk.Frame(
            placeholder_frame,
            bg=self.colors["panel_alt"],
            highlightthickness=1,
            highlightbackground=self.colors["border"]
        )
        center_frame.pack(fill=tk.BOTH, expand=True)

        main_title = tk.Label(
            center_frame,
            text="Coming Soon",
            font=("Bahnschrift SemiBold", 28),
            fg=self.colors["text"],
            bg=self.colors["panel_alt"]
        )
        main_title.pack(pady=(80, 20))

        message_label = tk.Label(
            center_frame,
            text=message,
            font=("Segoe UI", 12),
            fg=self.colors["text_secondary"],
            bg=self.colors["panel_alt"],
            wraplength=680,
            justify=tk.CENTER
        )
        message_label.pack()

        if has_log:
            log_panel = LogPanel(placeholder_frame, title=f"{title} Activity")
            log_panel.pack(fill=tk.X, pady=(10, 0))
            log_panel.add_log(f"{title} loaded")
            self.view_log_panels[view_id] = log_panel

    def _switch_view(self, view_id: str):
        """Switch to the selected view."""
        for view in self.views.values():
            view.pack_forget()

        self.views[view_id].pack(fill=tk.BOTH, expand=True)
        self.current_view = view_id
        title, subtitle = self.view_meta.get(view_id, (view_id.title(), ""))
        self.content_title_label.config(text=title)
        self.content_subtitle_label.config(text=subtitle)
        self._apply_nav_styles(view_id)

    def _process_embed(self, embed):
        """Process embed to match against products and transform."""
        embed_dict = embed.to_dict()

        # Debug: log all field names
        field_names = [f.get("name", "") for f in embed_dict.get("fields", [])]
        print(f"Debug - Embed fields: {field_names}")
        if self.debug_logging:
            self.log_message(f"🔍 Debug - Fields: {field_names}")

        # 1. Find SKU in embed fields - prioritize SKU field over product/name fields
        sku_value = None
        # First pass: look for SKU-specific fields
        sku_priority_fields = ["sku", "title/sku"]
        for field in embed_dict.get("fields", []):
            field_name = field.get("name", "").strip().lower()
            if field_name in sku_priority_fields:
                sku_value = field.get("value", "").strip()
                print(f"Debug - Found SKU field '{field_name}': {sku_value}")
                if self.debug_logging:
                    self.log_message(f"🔍 Debug - Found SKU field '{field_name}': {sku_value}")
                break
        # Second pass: only use title/product if no SKU field found
        if not sku_value:
            for field in embed_dict.get("fields", []):
                field_name = field.get("name", "").strip().lower()
                if field_name in ["title", "product"]:
                    sku_value = field.get("value", "").strip()
                    print(f"Debug - Found SKU field '{field_name}': {sku_value}")
                    if self.debug_logging:
                        self.log_message(f"🔍 Debug - Found SKU field '{field_name}': {sku_value}")
                    break

        if not sku_value:
            print(f"Debug - No SKU field found in embed")
            if self.debug_logging:
                self.log_message(f"🔍 Debug - No SKU field found in embed")

        # 2. Match against products
        product = None
        if sku_value and hasattr(self, 'bot') and self.bot.sku_data:
            print(f"Debug - Looking up SKU: {sku_value}")
            print(f"Debug - SKU data keys: {list(self.bot.sku_data.keys())[:5]}...")  # Show first 5
            if self.debug_logging:
                self.log_message(f"🔍 Debug - Looking up SKU: {sku_value}, bot.sku_data has {len(self.bot.sku_data)} products")
            # Check SKU, SKU2, Name
            for key in ['sku', 'sku2', 'name']:
                for sku, data in self.bot.sku_data.items():
                    if data.get(key, "").upper() == sku_value.upper():
                        product = data
                        print(f"Debug - Matched product: {product.get('name')}")
                        if self.debug_logging:
                            self.log_message(f"🔍 Debug - Matched! Product: {product.get('name')}, Platform: {product.get('platform')}")
                        break
                if product:
                    break
        else:
            if not hasattr(self, 'bot'):
                print(f"Debug - No bot attribute")
                if self.debug_logging:
                    self.log_message(f"🔍 Debug - No bot attribute")
            elif not self.bot.sku_data:
                print(f"Debug - No sku_data or empty")
                if self.debug_logging:
                    self.log_message(f"🔍 Debug - sku_data is empty ({len(self.bot.sku_data) if hasattr(self, 'bot') and self.bot.sku_data else 0} products)")

        # 3. Transform if matched
        if product:
            # Remove proxy/offer id fields
            fields = [f for f in embed_dict.get("fields", [])
                      if f.get("name", "").strip().lower() not in ["proxy", "offer id"]]
            embed_dict["fields"] = fields

            # Update title (without quotes)
            platform = product.get("platform", "Unknown")
            embed_dict["title"] = f"[{platform.capitalize()} Restock] - {product['name']}"

            # Add URL from product if available
            product_url = product.get("url", "")
            if product_url:
                embed_dict["url"] = product_url

            # Update footer with timestamp
            footer_text = f"FrontLines - SKUtto - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # Get the footer icon URL from config
            footer_icon = self.db.get_config("footer_icon_url", "")

            if footer_icon:
                embed_dict["footer"] = {"text": footer_text, "icon_url": footer_icon}
            else:
                embed_dict["footer"] = {"text": footer_text}

            # Store role_id from product for pinging
            embed_dict["role_id"] = product.get("roleid", "")

            # Store matched SKU for duplicate checking
            embed_dict["matched_sku"] = sku_value

            # Keep the original timestamp from the embed (don't delete it)

        return embed_dict

    def _process_checkout_embed(self, embed_dict: dict) -> dict:
        """Strip sensitive PII fields from a checkout embed before forwarding.

        Amazon checkouts (detected via site field containing 'amazon') retain
        the email field so it remains visible in the forwarded embed.
        """
        strip_set = {
            "order email", "order id", "order link",
            "account", "email", "purchase id",
            "offer id", "proxy"
        }

        # Detect Amazon checkout by site field value
        fields_list = embed_dict.get("fields", [])
        is_amazon = any(
            f.get("name", "").strip().lower() == "site" and
            "amazon" in f.get("value", "").strip().lower()
            for f in fields_list
        )
        if is_amazon:
            strip_set = strip_set - {"email"}

        fields = [f for f in fields_list
                  if f.get("name", "").strip().lower() not in strip_set]
        embed_dict["fields"] = fields
        return embed_dict

    async def _handle_checkout(self, message, bot):
        """Handle checkout notifications - find email in embed and DM user."""
        import re

        # Ignore messages from our own bot
        if message.author.bot and message.author.id == bot.bot.user.id:
            return

        self.log_message(f"📦 Checkout message from #{message.channel.name}: {message.author.display_name}")

        # Extract emails from embed fields and message content
        emails_found = set()

        def extract_emails(text):
            """Extract plain emails from text, stripping hyperlinks."""
            if not text:
                return set()
            # Remove markdown links: [email@example.com](mailto:email@example.com)
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
            # Remove mailto: prefix
            text = re.sub(r'mailto:', '', text)
            # Extract plain emails
            found = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
            return set(found)

        # Check embed fields
        for embed in message.embeds:
            embed_dict = embed.to_dict()
            # Check field values
            for field in embed_dict.get("fields", []):
                value = field.get("value", "")
                emails_found.update(extract_emails(value))
            # Check embed description
            if embed.description:
                emails_found.update(extract_emails(embed.description))
            # Check embed title
            if embed.title:
                emails_found.update(extract_emails(embed.title))

        # Also check message content
        if message.content:
            emails_found.update(extract_emails(message.content))

        self.log_message(f"🔍 Found emails in checkout: {emails_found}")

        # Look up each email and send DM with rate limiting
        for i, email in enumerate(emails_found):
            # Rate limit: 1 DM per second to avoid Discord rate limits
            if i > 0:
                import asyncio
                await asyncio.sleep(1)
            discord_id = self.bot.email_lookup.get(email.lower())
            if discord_id:
                try:
                    user = await bot.bot.fetch_user(discord_id)
                    if user:
                        # Create DM with success message
                        dm_content = "🎉 **Successful Checkout!**"

                        # Forward the embed if present
                        if message.embeds:
                            for embed in message.embeds:
                                await user.send(dm_content, embed=embed)
                        else:
                            await user.send(dm_content)

                        self.log_message(f"✅ Sent checkout notification to {email} (Discord: {discord_id})")
                except Exception as e:
                    self.log_message(f"⚠️ Failed to DM {email}: {e}")
            else:
                self.log_message(f"❓ Email {email} not found in database")

        # Forward stripped checkout embeds to checkouts target channel
        if self.bot.checkouts_target_channel_id and message.embeds:
            target_channel = bot.bot.get_channel(self.bot.checkouts_target_channel_id)
            if target_channel:
                for embed in message.embeds:
                    try:
                        processed = self._process_checkout_embed(embed.to_dict())
                        new_embed = discord.Embed.from_dict(processed)
                        await target_channel.send(embed=new_embed)
                    except Exception as e:
                        self.log_message(f"⚠️ Failed to forward checkout embed: {e}")
                self.log_message(
                    f"📤 Forwarded {len(message.embeds)} checkout embed(s) to checkouts target channel"
                )
            else:
                self.log_message(
                    f"⚠️ Checkouts target channel {self.bot.checkouts_target_channel_id} not found"
                )

    async def _handle_message(self, message, bot):
        """Handle messages from source channel - forward to target and log."""
        print(f"DEBUG: _handle_message called! Channel: {message.channel.name}, Author: {message.author}")
        # Ignore messages from OUR OWN bot to avoid loops
        if message.author.bot and message.author.id == bot.bot.user.id:
            print("DEBUG: Ignoring our own bot message (loop prevention)")
            return

        # Get channel ID as int for comparison
        msg_channel_id = int(message.channel.id)

        # Debug: log what we're comparing
        print(f"Debug - Message channel ID: {msg_channel_id}, Bot source channel: {self.bot.source_channel_id}, Checkouts channel: {self.bot.checkouts_channel_id}")

        # Check if message is from the checkouts channel
        if self.bot.checkouts_channel_id and msg_channel_id == self.bot.checkouts_channel_id:
            # Handle checkout notification
            await self._handle_checkout(message, bot)
            return

        # Check if message is from the source channel
        if self.bot.source_channel_id is None:
            print("Source channel ID is None!")
            return
        if msg_channel_id != self.bot.source_channel_id:
            print(f"Message not from source channel (expected {self.bot.source_channel_id}, got {msg_channel_id})")
            return

        # Log the received message to GUI
        content_preview = message.content[:50] + "..." if len(message.content) > 50 else message.content
        self.log_message(f"📥 Message from #{message.channel.name}: {message.author.display_name} - {content_preview}")

        # Forward to target channel if different from source
        if self.bot.target_channel_id and msg_channel_id != self.bot.target_channel_id:
            target_channel = bot.bot.get_channel(self.bot.target_channel_id)
            if target_channel:
                # Forward the message with embeds (processed)
                try:
                    if message.embeds:
                        self.log_message(f"🔍 Received {len(message.embeds)} embed(s)")
                        for embed in message.embeds:
                            processed = self._process_embed(embed)
                            # Debug: log the processed embed title
                            title = processed.get('title', 'No title')
                            fields_count = len(processed.get('fields', []))
                            self.log_message(f"🔍 Processed embed: '{title}' with {fields_count} fields")

                            # Check for duplicate
                            matched_sku = processed.get('matched_sku', '')
                            if matched_sku:
                                import time
                                current_time = time.time()
                                last_forwarded = self.recent_forwards.get(matched_sku, 0)
                                if current_time - last_forwarded < self.duplicate_timeout:
                                    self.log_message(f"⏭️ Skipping duplicate: {matched_sku} (within {self.duplicate_timeout}s)")
                                    continue

                            new_embed = discord.Embed.from_dict(processed)

                            # Send role ping if enabled and role_id exists in product (separate message first)
                            role_id = processed.get("role_id", "").strip()
                            if self.bot.enable_ping and role_id and role_id.isdigit():
                                mention = f"<@&{role_id}> - {title}"
                                self.log_message(f"📣 Pinging role: {role_id}")
                                await target_channel.send(content=mention)
                            await target_channel.send(embed=new_embed)

                            # Record forward time for duplicate check
                            if matched_sku:
                                import time
                                self.recent_forwards[matched_sku] = time.time()
                        self.log_message(f"📤 Forwarded {len(message.embeds)} embed(s) to target channel")
                    elif message.content:
                        await target_channel.send(message.content)
                        self.log_message(f"📤 Forwarded message to target channel")
                except Exception as e:
                    import traceback
                    self.log_message(f"⚠️ Failed to forward message: {e}")
                    self.log_message(f"⚠️ Traceback: {traceback.format_exc()}")

    def start_bot(self):
        """Start the Discord bot."""
        if not self.bot.token:
            self.root.after(0, self._add_log_to_panel, "❌ Bot token is not configured. Go to Settings tab.")
            return

        if not self.bot.source_channel_id:
            self.root.after(0, self._add_log_to_panel, "❌ Source channel not configured.")
            return

        if not self.bot.target_channel_id:
            self.root.after(0, self._add_log_to_panel, "❌ Target channel not configured.")
            return

        # Show loading indicator
        self._show_loading()

        # Set config on bot
        self.bot.set_config(
            self.bot.source_channel_id,
            self.bot.target_channel_id,
            self.bot.checkouts_channel_id or 0,
            self.bot.checkouts_target_channel_id or 0,
            self.bot.admin_channel_id or 0
        )

        # Refresh data
        self.bot.refresh_data()
        self.bot.set_sku_data(self.products_tab.sku_data)

        self.root.after(0, self._add_log_to_panel, "🔄 Starting bot...")

        # Set up callbacks with proper message handler
        self.bot.set_on_ready(self._on_bot_ready)
        self.bot.set_on_message(self._handle_message)
        self.bot.set_command_callback(self.log_message)
        self.bot.set_on_email_changed(self._on_email_changed)

        self.bot_thread = self.bot.start()

        # Update UI
        self._set_status_badge(
            self.status_badge,
            self.status_indicator,
            self.status_circle,
            self.status_label,
            "starting",
            "Starting"
        )
        self._set_action_button_state(self.start_btn, False)
        self._set_action_button_state(self.stop_btn, True)
        self._update_nav_indicator('skutto', True)

    async def _on_bot_ready(self, bot):
        """Callback when bot is ready."""
        self.root.after(0, self._update_status_online)
        # Log bot connection details to GUI
        self.root.after(0, self._add_log_to_panel, f"✅ Bot connected as {bot.user}")
        self.root.after(0, self._add_log_to_panel, f"📍 Listening in channel ID: {self.bot.source_channel_id}")
        self.root.after(0, self._add_log_to_panel, f"📍 Forwarding to channel ID: {self.bot.target_channel_id}")

    async def _on_email_changed(self):
        """Callback when email is added or removed via bot command."""
        self.root.after(0, self.emails_tab.load_emails)

    def _update_status_online(self):
        """Update status to online."""
        self._hide_loading()
        self._set_status_badge(
            self.status_badge,
            self.status_indicator,
            self.status_circle,
            self.status_label,
            "running",
            "Running"
        )
        self.log_message("✅ Bot is online!")

    def _show_loading(self):
        """Show the loading indicator."""
        self.loading_bar.start(10)
        self.loading_frame.pack(anchor="w", pady=(10, 0))

    def _hide_loading(self):
        """Hide the loading indicator."""
        self.loading_bar.stop()
        self.loading_frame.pack_forget()

    def _update_status_offline(self):
        """Update status to offline after bot stops."""
        self._hide_loading()
        self._set_status_badge(
            self.status_badge,
            self.status_indicator,
            self.status_circle,
            self.status_label,
            "offline",
            "Offline"
        )
        self._set_action_button_state(self.start_btn, True)
        self._set_action_button_state(self.stop_btn, False)
        self._update_nav_indicator('skutto', False)
        self.log_message("⏹ Bot stopped")

    def stop_bot(self):
        """Stop the Discord bot."""
        self.root.after(0, self._add_log_to_panel, "🛑 Stopping bot...")
        self._show_loading()

        # Run stop in a separate thread to avoid freezing UI
        def do_stop():
            try:
                self.bot.stop_sync()
            except Exception as e:
                self.root.after(0, self._add_log_to_panel, f"Error stopping bot: {e}")
            finally:
                # Update UI after bot stops
                self.root.after(0, self._update_status_offline)

        import threading
        threading.Thread(target=do_stop, daemon=True).start()

    def _setup_system_tray(self):
        """Setup system tray icon and menu."""
        try:
            import pystray
            from PIL import Image
            import sys
            import os

            # Load icon image - use exe directory for installed version
            if getattr(sys, 'frozen', False):
                # Running as bundled exe - icon is in _internal folder
                icon_path = os.path.join(os.path.dirname(sys.executable), "_internal", "Bag_Safari_Ball_SV_Sprite.png")
            else:
                # Running in development
                icon_path = "Bag_Safari_Ball_SV_Sprite.png"

            self._tray_icon_image = Image.open(icon_path)

            # Create menu items
            def show_window(icon, item):
                self.root.after(0, self._show_from_tray)

            def exit_app(icon, item):
                self.root.after(0, self._force_exit)

            menu = pystray.Menu(
                pystray.MenuItem("Show", show_window),
                pystray.MenuItem("Exit", exit_app)
            )

            # Create tray icon
            self._tray_icon = pystray.Icon(
                "FrontLinesMonitor",
                self._tray_icon_image,
                "FrontLines Monitor Suite",
                menu
            )

            # Run tray icon in separate thread
            import threading
            self._tray_thread = threading.Thread(target=self._tray_icon.run, daemon=True)
            self._tray_thread.start()

            # Handle minimize to tray - poll window state
            self._check_minimize_state()

        except Exception as e:
            print(f"System tray setup failed: {e}")

    def _check_minimize_state(self):
        """Poll window state to detect minimize."""
        if hasattr(self, '_was_minimized'):
            # Check if we were minimized and now restored
            if self._was_minimized and self.root.state() != 'iconic':
                self._was_minimized = False

        # Check if window is minimized
        if self.root.state() == 'iconic' and self.minimize_to_tray_var.get():
            if not hasattr(self, '_was_minimized') or not self._was_minimized:
                print("Window minimized, hiding to tray")
                self._was_minimized = True
                self.root.withdraw()
                if hasattr(self, '_tray_icon'):
                    self._tray_icon.notify("FrontLines Monitor Suite", "Minimized to system tray")

        # Poll every 500ms
        self.root.after(500, self._check_minimize_state)

    def _load_minimize_to_tray_setting(self):
        """Load minimize to tray setting from database."""
        try:
            value = self.db.get_config("minimize_to_tray")
            if value is not None:
                self.minimize_to_tray_var.set(value.lower() == "true")
        except Exception as e:
            print(f"Failed to load minimize to tray setting: {e}")

        # Bind checkbox change to save setting
        self.minimize_to_tray_checkbox.config(
            command=self._save_minimize_to_tray_setting
        )

    def _save_minimize_to_tray_setting(self):
        """Save minimize to tray setting to database."""
        try:
            value = "true" if self.minimize_to_tray_var.get() else "false"
            self.db.set_config("minimize_to_tray", value)
        except Exception as e:
            print(f"Failed to save minimize to tray setting: {e}")

    def _minimize_to_tray(self):
        """Minimize window to system tray."""
        print("_minimize_to_tray called")
        self.root.withdraw()
        if hasattr(self, '_tray_icon'):
            print("Sending tray notification")
            self._tray_icon.notify("FrontLines Monitor Suite", "Minimized to system tray")

    def _show_from_tray(self):
        """Show window from system tray."""
        self.root.deiconify()
        self.root.state('normal')
        self.root.lift()
        self.root.focus_force()

    def _force_exit(self):
        """Force exit application."""
        # Stop tray icon
        if hasattr(self, '_tray_icon'):
            self._tray_icon.stop()
        # Exit
        self.root.quit()
        self.root.destroy()
        import sys
        sys.exit()

    def on_close(self):
        """Handle window close - exit the application."""
        self._exit_application()

    def _exit_application(self):
        """Exit the application completely."""
        # Stop tray icon if running
        if hasattr(self, '_tray_icon'):
            try:
                self._tray_icon.stop()
            except Exception:
                pass

        if self.bot.is_running():
            self.stop_bot()
            self._show_loading()
            self._wait_and_close()
        else:
            self.root.destroy()

    def _wait_and_close(self):
        """Wait for bot to stop, then close the window."""
        if self.bot.is_running():
            # Check again in 500ms
            self.root.after(500, self._wait_and_close)
        else:
            self._hide_loading()
            # Stop tray icon
            if hasattr(self, '_tray_icon'):
                try:
                    self._tray_icon.stop()
                except Exception:
                    pass
            self.root.destroy()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = MainApplication(root)
    root.mainloop()


if __name__ == "__main__":
    main()
