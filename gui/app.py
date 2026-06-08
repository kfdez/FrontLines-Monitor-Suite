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
from core.ws_publisher import publish_trigger
from core.hv_monitor import HVMonitor
from core.shopify_monitor import ShopifyMonitor
from core.tasks import TasksManager
from gui.tabs.products_tab import ProductsTab
from gui.tabs.emails_tab import EmailsTab
from gui.tabs.settings_tab import SettingsTab
from gui.tabs.hv_monitor_tab import HVMonitorTab
from gui.tabs.shopify_monitor_tab import ShopifyMonitorTab
from gui.tabs.proxies_tab import ProxiesTab
from modules.skutto.unlock_events import (
    is_pokemoncenter_module_unlocked,
    POKEMONCENTER_ROLE_MENTION,
    reserve_unlock_event,
)


class ColoredButton(ttk.Button):
    """Custom styled button."""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(style="Custom.TButton")


class LogPanel(ttk.Frame):
    """Scrolling log panel for bot events."""

    MAX_LINES = 1000  # Maximum lines to keep in log

    def __init__(self, parent):
        super().__init__(parent)
        self._create_ui()

    def _create_ui(self):
        """Create the log panel UI."""
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

        ttk.Label(header_frame, text="📋 Activity Log", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

        clear_btn = ttk.Button(header_frame, text="Clear", command=self.clear_log, width=8)
        clear_btn.pack(side=tk.RIGHT)

        # Log text area with styling
        self.log_text = tk.Text(
            self,
            height=8,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#00ff00",
            insertbackground="white",
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
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

        # Custom button style
        style.configure(
            "Custom.TButton",
            padding=10,
            font=("Segoe UI", 10)
        )

        # Success button (green)
        style.configure(
            "Success.TButton",
            padding=10,
            font=("Segoe UI", 10, "bold"),
            background="#28a745"
        )

        # Danger button (red)
        style.configure(
            "Danger.TButton",
            padding=10,
            font=("Segoe UI", 10)
        )

        # Tab style
        style.configure(
            "Custom.TNotebook",
            background="#2d2d30"
        )
        style.configure(
            "Custom.TNotebook.Tab",
            padding=[15, 8],
            font=("Segoe UI", 10)
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

        # WebSocket trigger config
        self.ws_trigger_url = self.db.get_config("ws_trigger_url", "")
        self.ws_trigger_token = self.db.get_config("ws_trigger_token", "")

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
        if module not in self.nav_buttons:
            return

        btn_data = self.nav_buttons[module]

        # Skip if this button doesn't have an indicator (e.g., proxies)
        if not btn_data.get('has_indicator', True):
            return

        btn = btn_data['btn']

        # Use the stored base name (without indicator)
        base_text = btn_data['expanded']

        # Update with new indicator using colored circles
        indicator = '●' if running else '○'
        new_text = f"{indicator} {base_text}"

        if running:
            btn.config(text=new_text, fg="#28a745")  # Green
        else:
            btn.config(text=new_text, fg="#dc3545")  # Red

        # Keep expanded updated with base name (not including indicator)
        btn_data['expanded'] = base_text

    def _create_ui(self):
        """Create the main UI."""
        # Main container - horizontal layout
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        # === SIDEBAR NAVIGATION ===
        self.sidebar_frame = tk.Frame(main_container, bg="#252526")
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar_frame.config(width=200)
        self.sidebar_expanded = True
        self.sidebar_width = 200

        # App title in sidebar
        self.sidebar_title = tk.Label(
            self.sidebar_frame,
            text="FrontLines\nMonitor Suite",
            font=("Segoe UI", 12, "bold"),
            bg="#252526",
            fg="white",
            pady=15,
            justify=tk.CENTER
        )
        self.sidebar_title.pack()

        # Minimize to tray checkbox
        self.minimize_to_tray_var = tk.BooleanVar(value=False)
        self.minimize_to_tray_checkbox = tk.Checkbutton(
            self.sidebar_frame,
            text="Minimize to tray",
            variable=self.minimize_to_tray_var,
            bg="#252526",
            fg="white",
            selectcolor="#252526",
            activebackground="#252526",
            activeforeground="white",
            pady=5
        )
        self.minimize_to_tray_checkbox.pack(pady=(0, 10))

        # Load minimize to tray setting
        self._load_minimize_to_tray_setting()

        # Collapse/expand button
        self.collapse_btn = tk.Button(
            self.sidebar_frame,
            text="◀",
            font=("Segoe UI", 10),
            bg="#252526",
            fg="white",
            relief=tk.FLAT,
            padx=5,
            pady=5,
            cursor="hand2",
            command=self._toggle_sidebar
        )
        self.collapse_btn.pack(side=tk.BOTTOM, pady=10)

        # Navigation buttons
        self.nav_buttons = {}
        # Format: (view_id, expanded_text, collapsed_text)
        views = [
            ("skutto", "SKUtto", "[S]"),
            ("shopify", "Shopify Monitor", "[$]"),
            ("hobbiesville", "Hobbiesville", "[H]"),
            ("proxies", "🌐 Proxies", "[P]"),  # Proxies doesn't get indicator
        ]

        for view_id, expanded_text, collapsed_text in views:
            # Skip indicator for proxies
            if view_id == "proxies":
                btn_text = expanded_text
                btn_fg = "white"
            else:
                btn_text = f"○ {expanded_text}"
                btn_fg = "#dc3545"  # Red for stopped

            btn = tk.Button(
                self.sidebar_frame,
                text=btn_text,
                font=("Segoe UI", 11),
                bg="#2d2d30" if view_id != "skutto" else "#0e639c",
                fg=btn_fg,
                relief=tk.FLAT,
                anchor="w",
                padx=15,
                pady=12,
                cursor="hand2",
                command=lambda v=view_id: self._switch_view(v)
            )
            btn.pack(fill=tk.X, padx=5, pady=2)
            self.nav_buttons[view_id] = {
                'btn': btn,
                'expanded': expanded_text,  # Store base name without indicator
                'collapsed': collapsed_text,
                'has_indicator': view_id != "proxies"  # Flag to track if this button has indicator
            }

        # Track which modules are running for indicator updates
        self._module_status = {
            'skutto': False,
            'hobbiesville': False,
            'shopify': False
        }

        # === CONTENT AREA ===
        # Container for the right side
        content_container = ttk.Frame(main_container)
        content_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # === VIEW CONTAINER ===
        self.views_container = ttk.Frame(content_container)
        self.views_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create views dictionary
        self.views = {}
        self.view_log_panels = {}

        # Create SKUtto view (current implementation)
        self._create_skutto_view(content_container)

        # Create Hobbiesville (HV Monitor) view
        self._create_hv_monitor_view(content_container)

        # Create Shopify Monitor view
        self._create_shopify_monitor_view(content_container)

        # Create Proxies view
        self._create_proxies_view(content_container)

        # Set initial view (show SKUtto by default)
        self._switch_view("skutto")
        self.current_view = "skutto"

    def _toggle_sidebar(self):
        """Toggle the sidebar collapsed/expanded."""
        if self.sidebar_expanded:
            # Collapse
            self.sidebar_frame.config(width=40)
            self.sidebar_title.pack_forget()
            for btn_data in self.nav_buttons.values():
                btn_data['btn'].config(text=btn_data['collapsed'])
                btn_data['btn'].pack_forget()
            self.collapse_btn.config(text="▶")
            self.sidebar_expanded = False
        else:
            # Expand
            self.sidebar_frame.config(width=200)
            self.sidebar_title.pack()
            for btn_data in self.nav_buttons.values():
                btn_data['btn'].config(text=btn_data['expanded'])
                btn_data['btn'].pack(fill=tk.X, padx=5, pady=2)
            self.collapse_btn.config(text="◀")
            self.sidebar_expanded = True

    def _create_skutto_view(self, parent):
        """Create the SKUtto view with tabs, header controls, and log."""
        skutto_frame = ttk.Frame(self.views_container)
        self.views["skutto"] = skutto_frame

        # Header for SKUtto (with bot controls)
        header_frame = tk.Frame(skutto_frame, bg="#2d2d30", height=50)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)

        # Title
        tk.Label(
            header_frame,
            text="SKUtto",
            font=("Segoe UI", 14, "bold"),
            bg="#2d2d30",
            fg="white"
        ).pack(side=tk.LEFT, padx=10)

        # Bot status indicator
        self.status_indicator = tk.Canvas(header_frame, width=20, height=20, bg="#2d2d30", highlightthickness=0)
        self.status_indicator.pack(side=tk.RIGHT, padx=10)

        # Status circle
        self.status_circle = self.status_indicator.create_oval(2, 2, 18, 18, fill="#dc3545", outline="")

        # Status area frame (contains status + loading bar)
        status_area = tk.Frame(header_frame, bg="#2d2d30")
        status_area.pack(side=tk.RIGHT, padx=5)

        # Status label
        self.status_label = tk.Label(
            status_area,
            text="Offline",
            font=("Segoe UI", 10),
            bg="#2d2d30",
            fg="#dc3545"
        )
        self.status_label.pack()

        # Loading indicator (progress bar) - initially hidden
        self.loading_frame = tk.Frame(status_area, bg="#2d2d30")

        self.loading_bar = ttk.Progressbar(
            self.loading_frame,
            mode='indeterminate',
            length=60,
            takefocus=False
        )
        self.loading_bar.pack(pady=2)

        # Control buttons in header
        self.start_btn = tk.Button(
            header_frame,
            text="▶ Start",
            command=self.start_bot,
            bg="#28a745",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2"
        )
        self.start_btn.pack(side=tk.RIGHT, padx=5, pady=10)

        self.stop_btn = tk.Button(
            header_frame,
            text="⏹ Stop",
            command=self.stop_bot,
            bg="#dc3545",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.RIGHT, padx=5, pady=10)

        # Initially hide the loading frame
        self.loading_frame.pack_forget()

        # Create notebook for tabs
        self.notebook = ttk.Notebook(skutto_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.products_tab = ProductsTab(self.notebook, self)
        self.emails_tab = EmailsTab(self.notebook, self)
        self.settings_tab = SettingsTab(self.notebook, self)

        # Add tabs to notebook
        self.notebook.add(self.products_tab, text="📦 Products")
        self.notebook.add(self.emails_tab, text="📧 Emails")
        self.notebook.add(self.settings_tab, text="⚙️ Settings")

        # Log panel for SKUtto
        self.log_panel = LogPanel(skutto_frame)
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
        hv_frame = ttk.Frame(self.views_container)
        self.views["hobbiesville"] = hv_frame

        # Header for HV Monitor (with controls)
        header_frame = tk.Frame(hv_frame, bg="#2d2d30", height=50)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)

        # Title
        tk.Label(
            header_frame,
            text="Hobbiesville Monitor",
            font=("Segoe UI", 14, "bold"),
            bg="#2d2d30",
            fg="white"
        ).pack(side=tk.LEFT, padx=10)

        # HV Monitor status indicator
        self.hv_status_indicator = tk.Canvas(header_frame, width=20, height=20, bg="#2d2d30", highlightthickness=0)
        self.hv_status_indicator.pack(side=tk.RIGHT, padx=10)

        # Status circle
        self.hv_status_circle = self.hv_status_indicator.create_oval(2, 2, 18, 18, fill="#dc3545", outline="")

        # Status area frame
        hv_status_area = tk.Frame(header_frame, bg="#2d2d30")
        hv_status_area.pack(side=tk.RIGHT, padx=5)

        # Status label
        self.hv_status_label = tk.Label(
            hv_status_area,
            text="Offline",
            font=("Segoe UI", 10),
            bg="#2d2d30",
            fg="#dc3545"
        )
        self.hv_status_label.pack()

        # Control buttons in header
        self.hv_start_btn = tk.Button(
            header_frame,
            text="▶ Start",
            command=self.start_hv_monitor,
            bg="#28a745",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2"
        )
        self.hv_start_btn.pack(side=tk.RIGHT, padx=5, pady=10)

        self.hv_stop_btn = tk.Button(
            header_frame,
            text="⏹ Stop",
            command=self.stop_hv_monitor,
            bg="#dc3545",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.hv_stop_btn.pack(side=tk.RIGHT, padx=5, pady=10)

        # Create HV Monitor tab
        self.hv_monitor_tab = HVMonitorTab(hv_frame, self)
        self.hv_monitor_tab.pack(fill=tk.BOTH, expand=True)

        # Log panel for HV Monitor
        self.hv_log_panel = LogPanel(hv_frame)
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
        self.hv_status_label.config(text="Running", fg="#28a745")
        self.hv_status_indicator.itemconfig(self.hv_status_circle, fill="#28a745")
        self.hv_start_btn.config(state=tk.DISABLED, bg="#6c757d")
        self.hv_stop_btn.config(state=tk.NORMAL, bg="#dc3545")
        self._update_nav_indicator('hobbiesville', True)
        self.hv_log_panel.add_log("Monitor started")

    def stop_hv_monitor(self):
        """Stop the HV Monitor."""
        self.hv_monitor.stop()
        self.hv_status_label.config(text="Offline", fg="#dc3545")
        self.hv_status_indicator.itemconfig(self.hv_status_circle, fill="#dc3545")
        self.hv_start_btn.config(state=tk.NORMAL, bg="#28a745")
        self.hv_stop_btn.config(state=tk.DISABLED, bg="#6c757d")
        self._update_nav_indicator('hobbiesville', False)
        self.hv_log_panel.add_log("Monitor stopped")

    def _create_shopify_monitor_view(self, parent):
        """Create the Shopify Monitor view."""
        shopify_frame = ttk.Frame(self.views_container)
        self.views["shopify"] = shopify_frame

        # Header
        header_frame = tk.Frame(shopify_frame, bg="#2d2d30", height=50)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)

        # Title
        tk.Label(
            header_frame,
            text="Shopify Monitor",
            font=("Segoe UI", 14, "bold"),
            bg="#2d2d30",
            fg="white"
        ).pack(side=tk.LEFT, padx=10)

        # Shopify Monitor status indicator
        self.shopify_status_indicator = tk.Canvas(header_frame, width=20, height=20, bg="#2d2d30", highlightthickness=0)
        self.shopify_status_indicator.pack(side=tk.RIGHT, padx=10)

        # Status circle
        self.shopify_status_circle = self.shopify_status_indicator.create_oval(2, 2, 18, 18, fill="#dc3545", outline="")

        # Status area frame
        shopify_status_area = tk.Frame(header_frame, bg="#2d2d30")
        shopify_status_area.pack(side=tk.RIGHT, padx=5)

        # Status label
        self.shopify_status_label = tk.Label(
            shopify_status_area,
            text="Offline",
            font=("Segoe UI", 10),
            bg="#2d2d30",
            fg="#dc3545"
        )
        self.shopify_status_label.pack()

        # Control buttons in header
        self.shopify_start_btn = tk.Button(
            header_frame,
            text="▶ Start",
            command=self.start_shopify_monitor,
            bg="#28a745",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2"
        )
        self.shopify_start_btn.pack(side=tk.RIGHT, padx=5, pady=10)

        self.shopify_stop_btn = tk.Button(
            header_frame,
            text="⏹ Stop",
            command=self.stop_shopify_monitor,
            bg="#dc3545",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.shopify_stop_btn.pack(side=tk.RIGHT, padx=5, pady=10)

        # Create Shopify Monitor tab
        self.shopify_monitor_tab = ShopifyMonitorTab(shopify_frame, self)
        self.shopify_monitor_tab.pack(fill=tk.BOTH, expand=True)

        # Log panel for Shopify Monitor
        self.shopify_log_panel = LogPanel(shopify_frame)
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
            messagebox.showerror("Error", "Please configure stores in stores.txt first.")
            return

        if not self.shopify_monitor.keywords:
            self.shopify_log_panel.add_log("Error: No keywords configured")
            messagebox.showerror("Error", "Please configure keywords in keywords.txt first.")
            return

        self.shopify_monitor.start()
        self.shopify_status_label.config(text="Running", fg="#28a745")
        self.shopify_status_indicator.itemconfig(self.shopify_status_circle, fill="#28a745")
        self.shopify_start_btn.config(state=tk.DISABLED, bg="#6c757d")
        self.shopify_stop_btn.config(state=tk.NORMAL, bg="#dc3545")
        self._update_nav_indicator('shopify', True)
        self.shopify_log_panel.add_log("Monitor started")

    def stop_shopify_monitor(self):
        """Stop the Shopify Monitor."""
        self.shopify_monitor.stop()
        self.shopify_status_label.config(text="Offline", fg="#dc3545")
        self.shopify_status_indicator.itemconfig(self.shopify_status_circle, fill="#dc3545")
        self.shopify_start_btn.config(state=tk.NORMAL, bg="#28a745")
        self.shopify_stop_btn.config(state=tk.DISABLED, bg="#6c757d")
        self._update_nav_indicator('shopify', False)
        self.shopify_log_panel.add_log("Monitor stopped")

    def _update_shopify_button_states(self):
        """Update Shopify Monitor start/stop button states."""
        if self.shopify_monitor._running:
            self.shopify_start_btn.config(state=tk.DISABLED, bg="#6c757d")
            self.shopify_stop_btn.config(state=tk.NORMAL, bg="#dc3545")
        else:
            self.shopify_start_btn.config(state=tk.NORMAL, bg="#28a745")
            self.shopify_stop_btn.config(state=tk.DISABLED, bg="#6c757d")

    def _create_proxies_view(self, parent):
        """Create the Proxies view."""
        proxies_frame = ttk.Frame(self.views_container)
        self.views["proxies"] = proxies_frame

        # Header
        header_frame = tk.Frame(proxies_frame, bg="#2d2d30", height=40)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)

        # Title
        tk.Label(
            header_frame,
            text="Proxies",
            font=("Segoe UI", 14, "bold"),
            bg="#2d2d30",
            fg="white"
        ).pack(side=tk.LEFT, padx=10)

        # Create Proxies tab
        self.proxies_tab = ProxiesTab(proxies_frame, self)
        self.proxies_tab.pack(fill=tk.BOTH, expand=True)

    def _create_placeholder_view(self, view_id: str, title: str, message: str, has_log: bool = True):
        """Create a placeholder view."""
        placeholder_frame = ttk.Frame(self.views_container)
        self.views[view_id] = placeholder_frame

        # Mini header (no controls, just title)
        header_frame = tk.Frame(placeholder_frame, bg="#2d2d30", height=40)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)

        view_title = tk.Label(
            header_frame,
            text=title,
            font=("Segoe UI", 14, "bold"),
            bg="#2d2d30",
            fg="white"
        )
        view_title.pack(side=tk.LEFT, padx=10)

        # Center the content
        center_frame = ttk.Frame(placeholder_frame)
        center_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        main_title = tk.Label(
            center_frame,
            text="Coming Soon",
            font=("Segoe UI", 24, "bold"),
            fg="#888888"
        )
        main_title.pack(pady=(80, 20))

        # Message
        message_label = tk.Label(
            center_frame,
            text=message,
            font=("Segoe UI", 14),
            fg="#666666"
        )
        message_label.pack()

        # Log panel (only if has_log is True)
        if has_log:
            log_panel = LogPanel(placeholder_frame)
            log_panel.pack(fill=tk.X, pady=(10, 0))
            log_panel.add_log(f"{title} loaded")
            self.view_log_panels[view_id] = log_panel
        center_frame = ttk.Frame(placeholder_frame)
        center_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(
            center_frame,
            text=title,
            font=("Segoe UI", 24, "bold"),
            fg="#888888"
        )
        title_label.pack(pady=(100, 20))

        # Message
        message_label = tk.Label(
            center_frame,
            text=message,
            font=("Segoe UI", 14),
            fg="#666666"
        )
        message_label.pack()

    def _switch_view(self, view_id: str):
        """Switch to the selected view."""
        # Hide all views
        for view in self.views.values():
            view.pack_forget()

        # Show the selected view
        self.views[view_id].pack(fill=tk.BOTH, expand=True)

        # Update nav button styles
        for btn_id, btn_data in self.nav_buttons.items():
            if btn_id == view_id:
                btn_data['btn'].config(bg="#0e639c")
            else:
                btn_data['btn'].config(bg="#2d2d30")

        self.current_view = view_id

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

            # WebSocket trigger metadata
            ws_raw = product.get("send_to_websocket", "")
            embed_dict["ws_enabled"] = str(ws_raw).strip().upper() in ("TRUE", "1", "YES")
            embed_dict["ws_platform"] = platform.lower()

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

    async def _forward_module_unlock(self, message, bot):
        """Forward PokemonCenter module unlock alerts to the monitor channel."""
        if not message.embeds:
            return
        if not is_pokemoncenter_module_unlocked(message.content, message.embeds):
            return
        if not reserve_unlock_event(self.recent_forwards):
            self.log_message("Skipping duplicate PokemonCenter module unlock")
            return
        if not self.bot.target_channel_id:
            self.log_message("PokemonCenter module unlock target channel is not configured")
            return

        target_channel = bot.bot.get_channel(self.bot.target_channel_id)
        if not target_channel:
            self.log_message("PokemonCenter module unlock target channel not found")
            return

        for index, embed in enumerate(message.embeds):
            await target_channel.send(
                content=POKEMONCENTER_ROLE_MENTION if index == 0 else None,
                embed=discord.Embed.from_dict(embed.to_dict()),
            )
        self.log_message("Forwarded PokemonCenter module unlock to monitor channel")

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
            await self._forward_module_unlock(message, bot)
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

                            # Fire WebSocket trigger (non-blocking, fire-and-forget)
                            _matched_sku = processed.get("matched_sku")
                            _ws_enabled = processed.get("ws_enabled", False)
                            if _ws_enabled:
                                if self.ws_trigger_url and self.ws_trigger_token:
                                    import asyncio
                                    from functools import partial as _partial
                                    _fn = _partial(
                                        publish_trigger,
                                        self.ws_trigger_url,
                                        self.ws_trigger_token,
                                        processed.get("ws_platform", "costco"),
                                        _matched_sku or None,
                                        processed.get("url") or None,
                                    )
                                    asyncio.get_running_loop().run_in_executor(None, _fn)
                                    self.log_message(
                                        f"🌐 WS trigger queued — sku={_matched_sku} "
                                        f"platform={processed.get('ws_platform')}"
                                    )
                                else:
                                    self.log_message(
                                        f"⚠️ WS trigger skipped — URL or Token not set in Settings "
                                        f"(sku={_matched_sku})"
                                    )
                            elif _matched_sku:
                                # Product matched but Send To Websocket column is not TRUE
                                self.log_message(
                                    f"ℹ️ WS trigger skipped — '{_matched_sku}' matched but "
                                    f"Send To Websocket = FALSE (check column I, then reload Sheets)"
                                )

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
        self.status_label.config(text="Starting...", fg="orange")
        self.status_indicator.itemconfig(self.status_circle, fill="orange")
        self.start_btn.config(state=tk.DISABLED, bg="#6c757d")
        self.stop_btn.config(state=tk.NORMAL, bg="#dc3545")
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
        self.status_label.config(text="Online", fg="#28a745")
        self.status_indicator.itemconfig(self.status_circle, fill="#28a745")
        self.log_message("✅ Bot is online!")

    def _show_loading(self):
        """Show the loading indicator."""
        self.loading_bar.start(10)
        self.loading_frame.pack()

    def _hide_loading(self):
        """Hide the loading indicator."""
        self.loading_bar.stop()
        self.loading_frame.pack_forget()

    def _update_status_offline(self):
        """Update status to offline after bot stops."""
        self._hide_loading()
        self.status_label.config(text="Offline", fg="#dc3545")
        self.status_indicator.itemconfig(self.status_circle, fill="#dc3545")
        self.start_btn.config(state=tk.NORMAL, bg="#28a745")
        self.stop_btn.config(state=tk.DISABLED, bg="#6c757d")
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
