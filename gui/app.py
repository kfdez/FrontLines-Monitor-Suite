"""Main GUI application - FrontLines Monitor Suite."""
import tkinter as tk
from tkinter import ttk
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
from gui.tabs.products_tab import ProductsTab
from gui.tabs.emails_tab import EmailsTab
from gui.tabs.settings_tab import SettingsTab


class ColoredButton(ttk.Button):
    """Custom styled button."""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(style="Custom.TButton")


class LogPanel(ttk.Frame):
    """Scrolling log panel for bot events."""

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

    def clear_log(self):
        """Clear the log."""
        self.log_text.delete(1.0, tk.END)


class MainApplication:
    """Main application window - FrontLines Monitor Suite."""

    def __init__(self, root):
        self.root = root
        self.root.title("FrontLines Monitor Suite")
        self.root.geometry("1200x900")
        self.root.minsize(1000, 700)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Set window icon
        try:
            self.root.iconbitmap("favicon.ico")
        except Exception:
            pass

        # Configure custom styles
        self._configure_styles()

        # Initialize core components
        self.db = Database()
        self.sheets = SheetsManager()
        self.bot = DiscordBot("", self.db)

        # Bot state
        self.bot_thread = None

        # Load saved config
        self._load_config()

        # Create main UI
        self._create_ui()

        # Auto-start bot if enabled
        if self.auto_start:
            self.root.after(500, self.start_bot)

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
        self.bot.admin_channel_id = self._str_to_int(
            self.db.get_config("admin_channel_id", ""))
        self.bot.enable_ping = self.db.get_config("enable_ping", "false").lower() == "true"

        # Auto-start setting
        self.auto_start = self.db.get_config("auto_start", "false").lower() == "true"

    def _str_to_int(self, value: str) -> int:
        """Convert string to int safely."""
        try:
            return int(value) if value else None
        except (ValueError, TypeError):
            return None

    def log_message(self, message: str):
        """Add a message to the log panel."""
        if self.log_panel is not None:
            self.root.after(0, self._add_log_to_panel, message)

    def _add_log_to_panel(self, message: str):
        """Actually add the log message to the panel (called on main thread)."""
        if self.log_panel is not None:
            self.log_panel.add_log(message)

    def _create_ui(self):
        """Create the main UI."""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Top header bar
        header_frame = tk.Frame(main_container, bg="#1e1e1e", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        # Logo/Title
        title_label = tk.Label(
            header_frame,
            text="FrontLines Monitor Suite",
            font=("Segoe UI", 18, "bold"),
            bg="#1e1e1e",
            fg="white"
        )
        title_label.pack(side=tk.LEFT, padx=20)

        # Bot status indicator
        self.status_indicator = tk.Canvas(header_frame, width=20, height=20, bg="#1e1e1e", highlightthickness=0)
        self.status_indicator.pack(side=tk.RIGHT, padx=20)

        # Status circle
        self.status_circle = self.status_indicator.create_oval(2, 2, 18, 18, fill="#dc3545", outline="")

        # Status area frame (contains status + loading bar)
        status_area = tk.Frame(header_frame, bg="#1e1e1e")
        status_area.pack(side=tk.RIGHT, padx=5)

        # Status label
        self.status_label = tk.Label(
            status_area,
            text="Offline",
            font=("Segoe UI", 12),
            bg="#1e1e1e",
            fg="#dc3545"
        )
        self.status_label.pack()

        # Loading indicator (progress bar) - initially hidden
        self.loading_frame = tk.Frame(status_area, bg="#1e1e1e")

        self.loading_bar = ttk.Progressbar(
            self.loading_frame,
            mode='indeterminate',
            length=80,
            takefocus=False
        )
        self.loading_bar.pack(pady=2)

        # Control buttons in header
        self.start_btn = tk.Button(
            header_frame,
            text="▶ Start Bot",
            command=self.start_bot,
            bg="#28a745",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            padx=15,
            pady=5,
            cursor="hand2"
        )
        self.start_btn.pack(side=tk.RIGHT, padx=5, pady=10)

        self.stop_btn = tk.Button(
            header_frame,
            text="⏹ Stop Bot",
            command=self.stop_bot,
            bg="#dc3545",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            padx=15,
            pady=5,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.RIGHT, padx=5, pady=10)

        # Initially hide the loading frame
        self.loading_frame.pack_forget()

        # Content area with tabs
        content_frame = ttk.Frame(main_container)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.products_tab = ProductsTab(self.notebook, self)
        self.emails_tab = EmailsTab(self.notebook, self)
        self.settings_tab = SettingsTab(self.notebook, self)

        # Add tabs to notebook
        self.notebook.add(self.products_tab, text="📦 Products")
        self.notebook.add(self.emails_tab, text="📧 Emails")
        self.notebook.add(self.settings_tab, text="⚙️ Settings")

        # Log panel at bottom
        self.log_panel = LogPanel(main_container)
        self.log_panel.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Add welcome message
        self.log_panel.add_log("FrontLines Monitor Suite started")
        self.log_panel.add_log("Configure bot settings in the Settings tab")

        # Load data on startup
        self.products_tab.load_products()
        self.products_tab.load_pending()
        self.products_tab.load_platforms()
        self.emails_tab.load_emails()

    def _process_embed(self, embed):
        """Process embed to match against products and transform."""
        embed_dict = embed.to_dict()

        # Debug: log all field names
        field_names = [f.get("name", "") for f in embed_dict.get("fields", [])]
        print(f"Debug - Embed fields: {field_names}")

        # 1. Find SKU in embed fields
        sku_value = None
        for field in embed_dict.get("fields", []):
            field_name = field.get("name", "").strip().lower()
            if field_name in ["sku", "title/sku", "title"]:
                sku_value = field.get("value", "").strip()
                print(f"Debug - Found SKU field '{field_name}': {sku_value}")
                break

        if not sku_value:
            print(f"Debug - No SKU field found in embed")

        # 2. Match against products
        product = None
        if sku_value and hasattr(self, 'bot') and self.bot.sku_data:
            print(f"Debug - Looking up SKU: {sku_value}")
            print(f"Debug - SKU data keys: {list(self.bot.sku_data.keys())[:5]}...")  # Show first 5
            # Check SKU, SKU2, Name
            for key in ['sku', 'sku2', 'name']:
                for sku, data in self.bot.sku_data.items():
                    if data.get(key, "").upper() == sku_value.upper():
                        product = data
                        print(f"Debug - Matched product: {product.get('name')}")
                        break
                if product:
                    break
        else:
            if not hasattr(self, 'bot'):
                print(f"Debug - No bot attribute")
            elif not self.bot.sku_data:
                print(f"Debug - No sku_data or empty")

        # 3. Transform if matched
        if product:
            # Remove proxy/offer id fields
            fields = [f for f in embed_dict.get("fields", [])
                      if f.get("name", "").strip().lower() not in ["proxy", "offer id"]]
            embed_dict["fields"] = fields

            # Update title (without quotes)
            platform = product.get("platform", "Unknown")
            embed_dict["title"] = f"[{platform.capitalize()} Restock] - {product['name']}"

            # Update footer with SKUtto 3.0 and optional icon
            footer_text = "SKUtto 3.0"

            # Get the footer icon URL from config
            footer_icon = self.db.get_config("footer_icon_url", "")

            if footer_icon:
                embed_dict["footer"] = {"text": footer_text, "icon_url": footer_icon}
            else:
                embed_dict["footer"] = {"text": footer_text}

            # Store role_id from product for pinging
            embed_dict["role_id"] = product.get("roleid", "")

            # Keep the original timestamp from the embed (don't delete it)

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

        # Check embed fields
        for embed in message.embeds:
            embed_dict = embed.to_dict()
            # Check field values
            for field in embed_dict.get("fields", []):
                value = field.get("value", "")
                found = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', value)
                emails_found.update(found)
            # Check embed description
            if embed.description:
                found = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', embed.description)
                emails_found.update(found)
            # Check embed title
            if embed.title:
                found = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', embed.title)
                emails_found.update(found)

        # Also check message content
        if message.content:
            found = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', message.content)
            emails_found.update(found)

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
                            new_embed = discord.Embed.from_dict(processed)

                            # Send role ping if enabled and role_id exists in product
                            role_id = processed.get("role_id", "")
                            if self.bot.enable_ping and role_id:
                                ping_msg = f"<@&{role_id}>"
                                await target_channel.send(ping_msg, embed=new_embed)
                            else:
                                await target_channel.send(embed=new_embed)
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
            self.bot.admin_channel_id or 0
        )

        # Refresh data
        self.bot.refresh_data()
        self.bot.set_sku_data(self.products_tab.sku_data)

        self.root.after(0, self._add_log_to_panel, "🔄 Starting bot...")

        # Set up callbacks with proper message handler
        self.bot.set_on_ready(self._on_bot_ready)
        self.bot.set_on_message(self._handle_message)
        self.bot.set_on_email_changed(self._on_email_changed)

        self.bot_thread = self.bot.start()

        # Update UI
        self.status_label.config(text="Starting...", fg="orange")
        self.status_indicator.itemconfig(self.status_circle, fill="orange")
        self.start_btn.config(state=tk.DISABLED, bg="#6c757d")
        self.stop_btn.config(state=tk.NORMAL, bg="#dc3545")

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

    def on_close(self):
        """Handle window close."""
        if self.bot.is_running():
            from tkinter import messagebox
            answer = messagebox.askyesnocancel(
                "Exit Confirmation",
                "The bot is still running. Do you want to stop and exit?"
            )
            if answer is None:
                return
            elif answer:
                self.stop_bot()
                # Show loading and wait for bot to stop
                self._show_loading()
                self._wait_and_close()
                return
        self.root.destroy()

    def _wait_and_close(self):
        """Wait for bot to stop, then close the window."""
        if self.bot.is_running():
            # Check again in 500ms
            self.root.after(500, self._wait_and_close)
        else:
            self._hide_loading()
            self.root.destroy()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = MainApplication(root)
    root.mainloop()


if __name__ == "__main__":
    main()
