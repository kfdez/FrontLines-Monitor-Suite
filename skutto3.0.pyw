import threading
import asyncio
import sys
import io
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from tkinter import messagebox
import tkinter.filedialog as fd
import discord
import csv
import datetime
import re
import json
import os
from datetime import timezone

BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# Global placeholders to be assigned from GUI loaded data
email_lookup = {}
sku_data = {}
recent_skus = {}  # SKU: datetime
DUPLICATE_TIMEOUT = 500  # seconds

platform_map = {
    "walmart": ("walmart", "product"),
    "gamestop": ("gamestop", "product"),
    "amazon": ("amazonv3", "sku"),
    "costco": ("costco", "title/sku"),
    "bestbuy": ("bestbuy", "title/sku"),
    "popmart": ("popmart", "title/sku"),
    "queueit": ("queueit","Queue Pass"),
    "indigo": ("indigoca", "product"),
}

# ----------- GUI SETUP ---------------

class RedirectText(io.StringIO):
    def __init__(self, text_ctrl):
        super().__init__()
        self.text_ctrl = text_ctrl

    def write(self, s):
        self.text_ctrl.configure(state='normal')
        self.text_ctrl.insert(tk.END, s)
        self.text_ctrl.see(tk.END)
        self.text_ctrl.configure(state='disabled')

    def flush(self):
        pass

def log(message):
    print(message)


class DiscordBotGUI:
    def __init__(self, root):
        self.root = root
        root.title("SKUtto")
        root.geometry("1000x850")
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        #File paths
        self.email_csv_path = ""
        self.products_csv_path = ""


        # Set window icon .ico file
        try:
            root.iconbitmap("favicon.ico")
        except Exception as e:
            print(f"⚠️ Could not load icon: {e}")

        config_frame = tk.Frame(root)
        config_frame.pack(pady=10, fill=tk.X)

        # Bot token
        tk.Label(config_frame, text="Bot Token:", width=17, anchor='w').grid(row=0, column=0, sticky="w")
        self.token_entry = tk.Entry(config_frame, width=70, show="*")
        self.token_entry.grid(row=0, column=1, padx=5, pady=2)

        # Source channel ID
        tk.Label(config_frame, text="Source Channel ID:", width=17, anchor='w').grid(row=1, column=0, sticky="w")
        self.source_channel_entry = tk.Entry(config_frame, width=70)
        self.source_channel_entry.grid(row=1, column=1, padx=5, pady=2)

        # Target channel ID
        tk.Label(config_frame, text="Target Channel ID:", width=17, anchor='w').grid(row=2, column=0, sticky="w")
        self.target_channel_entry = tk.Entry(config_frame, width=70)
        self.target_channel_entry.grid(row=2, column=1, padx=5, pady=2)

        # Checkouts channel ID
        tk.Label(config_frame, text="Checkouts Channel ID:", width=17, anchor='w').grid(row=3, column=0, sticky="w")
        self.checkouts_channel_entry = tk.Entry(config_frame, width=70)
        self.checkouts_channel_entry.grid(row=3, column=1, padx=5, pady=2)

        # Queue bypass channel ID
        tk.Label(config_frame, text="Queue Bypass ID:", width=17, anchor='w').grid(row=4, column=0, sticky="w")
        self.queue_channel_entry = tk.Entry(config_frame, width=70)
        self.queue_channel_entry.grid(row=4, column=1, padx=5, pady=2)

        # Admin channel ID
        tk.Label(config_frame, text="Admin Channel ID:", width=17, anchor='w').grid(row=5, column=0, sticky="w")
        self.admin_channel_entry = tk.Entry(config_frame, width=70)
        self.admin_channel_entry.grid(row=5, column=1, padx=5, pady=2)
        

        # Control row
        control_frame = tk.Frame(root)
        control_frame.pack(pady=10, fill=tk.X)
        
        self.save_button = tk.Button(control_frame, text="Save Config", command=self.save_config)
        self.save_button.pack(side=tk.LEFT, padx=5)
        
        self.load_button = tk.Button(control_frame, text="Load Config", command=self.load_config)
        self.load_button.pack(side=tk.LEFT, padx=5)

        self.load_email_btn = tk.Button(control_frame, text="Load Email Lookup", command=self.load_email_csv)
        self.load_email_btn.pack(side=tk.LEFT, padx=5)
        
        self.load_products_btn = tk.Button(control_frame, text="Load Products", command=self.load_products_csv)
        self.load_products_btn.pack(side=tk.LEFT, padx=5)

        self.start_button = tk.Button(control_frame, text="Start Bot", command=self.start_bot)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(control_frame, text="Stop Bot", command=self.stop_bot, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(control_frame, text="Status: Offline", fg="red", font=("Arial", 14))
        self.status_label.pack(side=tk.LEFT, padx=5)

                
        # Email Lookup filter entry
        email_filter_frame = tk.Frame(root)
        email_filter_frame.pack(fill=tk.X, padx=10)
        tk.Label(email_filter_frame, text="Filter Emails:").pack(side=tk.LEFT)
        self.email_filter_var = tk.StringVar()
        self.email_filter_var.trace_add('write', self.filter_email_table)
        email_filter_entry = tk.Entry(email_filter_frame, textvariable=self.email_filter_var)
        email_filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Email Lookup preview frame with scrollbars
        email_preview_frame = tk.LabelFrame(root, text="Email Lookup Preview (Email -> DiscordID)")
        email_preview_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)

        email_tree_container = tk.Frame(email_preview_frame)
        email_tree_container.pack(fill=tk.BOTH, expand=True)

        self.email_tree = ttk.Treeview(email_tree_container, columns=("Email", "DiscordID"), show="headings")
        self.email_tree.heading("Email", text="Email", command=lambda: self.sort_treeview(self.email_tree, "Email", False))
        self.email_tree.heading("DiscordID", text="DiscordID", command=lambda: self.sort_treeview(self.email_tree, "DiscordID", False))
        self.email_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        email_vsb = ttk.Scrollbar(email_tree_container, orient="vertical", command=self.email_tree.yview)
        email_hsb = ttk.Scrollbar(email_tree_container, orient="horizontal", command=self.email_tree.xview)
        self.email_tree.configure(yscrollcommand=email_vsb.set, xscrollcommand=email_hsb.set)
        email_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        email_hsb.pack(side=tk.BOTTOM, fill=tk.X)        
        
        # Products filter entry
        products_filter_frame = tk.Frame(root)
        products_filter_frame.pack(fill=tk.X, padx=10)
        tk.Label(products_filter_frame, text="Filter Products:").pack(side=tk.LEFT)
        self.products_filter_var = tk.StringVar()
        self.products_filter_var.trace_add('write', self.filter_products_table)
        products_filter_entry = tk.Entry(products_filter_frame, textvariable=self.products_filter_var)
        products_filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Products preview frame with scrollbars
        products_preview_frame = tk.LabelFrame(root, text="Products Preview (SKU, Name, URL, RoleID)")
        products_preview_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)

        products_tree_container = tk.Frame(products_preview_frame)
        products_tree_container.pack(fill=tk.BOTH, expand=True)

        self.products_tree = ttk.Treeview(products_tree_container, columns=("SKU", "Name", "URL", "RoleID"), show="headings")
        for col in ("SKU", "Name", "URL", "RoleID"):
            self.products_tree.heading(col, text=col, command=lambda c=col: self.sort_treeview(self.products_tree, c, False))
        self.products_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        products_vsb = ttk.Scrollbar(products_tree_container, orient="vertical", command=self.products_tree.yview)
        products_hsb = ttk.Scrollbar(products_tree_container, orient="horizontal", command=self.products_tree.xview)
        self.products_tree.configure(yscrollcommand=products_vsb.set, xscrollcommand=products_hsb.set)
        products_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        products_hsb.pack(side=tk.BOTTOM, fill=tk.X)        

        # Logging window
        self.log_text = ScrolledText(root, state='disabled', height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
 
        # Redirect stdout and stderr to log_text
        sys.stdout = RedirectText(self.log_text)
        sys.stderr = RedirectText(self.log_text)

        self.bot_thread = None
        self.bot_loop = None

        # Hold loaded data here
        self.email_lookup = {}
        self.sku_data = {}

        # Load config if exists on startup
        self.load_config()

    def on_close(self):
        if self.bot_thread and self.bot_thread.is_alive():
            answer = tk.messagebox.askyesnocancel(
                "Exit Confirmation",
                "The bot is still running.\nDo you want to stop the bot and exit?",
            )
            if answer is None:  # Cancel
                return
            elif answer:  # Yes
                self.stop_bot()
                self.root.after(1000, self.check_bot_stopped_and_close)
                return
            else:  # No
                return
        else:
            self.root.destroy()

    def check_bot_stopped_and_close(self):
        if self.bot_thread and self.bot_thread.is_alive():
            self.root.after(500, self.check_bot_stopped_and_close)
        else:
            self.root.destroy()


    def save_config(self):
        config_data = {
            "bot_token": self.token_entry.get().strip(),
            "source_channel_id": self.source_channel_entry.get().strip(),
            "target_channel_id": self.target_channel_entry.get().strip(),
            "checkouts_channel_id": self.checkouts_channel_entry.get().strip(),
            "queue_channel_id": self.queue_channel_entry.get().strip(),
            "admin_channel_id": self.admin_channel_entry.get().strip(),
            "email_csv_path": self.email_csv_path,
            "products_csv_path": self.products_csv_path,
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=4)
            print("✅ Configuration saved.")
        except Exception as e:
            print(f"❌ Failed to save config: {e}")

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            print("⚠️ Config file not found, please enter config manually.")
            return
        try:
            with open(CONFIG_FILE, "r") as f:
                config_data = json.load(f)
            self.token_entry.delete(0, tk.END)
            self.token_entry.insert(0, config_data.get("bot_token", ""))

            self.source_channel_entry.delete(0, tk.END)
            self.source_channel_entry.insert(0, config_data.get("source_channel_id", ""))

            self.target_channel_entry.delete(0, tk.END)
            self.target_channel_entry.insert(0, config_data.get("target_channel_id", ""))

            self.checkouts_channel_entry.delete(0, tk.END)
            self.checkouts_channel_entry.insert(0, config_data.get("checkouts_channel_id", ""))
            
            self.queue_channel_entry.delete(0, tk.END)
            self.queue_channel_entry.insert(0, config_data.get("queue_channel_id",""))

            self.admin_channel_entry.delete(0, tk.END)
            self.admin_channel_entry.insert(0, config_data.get("admin_channel_id", ""))
            
            self.email_csv_path = config_data.get("email_csv_path", "")
            self.products_csv_path = config_data.get("products_csv_path", "")

            if self.email_csv_path and os.path.exists(self.email_csv_path):
                self.load_email_csv(self.email_csv_path)

            if self.products_csv_path and os.path.exists(self.products_csv_path):
                self.load_products_csv(self.products_csv_path)

            print("✅ Configuration loaded.")
        except Exception as e:
            print(f"❌ Failed to load config: {e}")

    def load_email_csv(self, path=None):
        if not path:
            path = fd.askopenfilename(title="Select Email Lookup CSV", filetypes=[("CSV Files", "*.csv")])
        if not path:
            return
        self.email_csv_path = path  # Save selected path
        try:
            with open(path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                self.email_lookup.clear()
                self.email_tree.delete(*self.email_tree.get_children())
                count = 0
                for row in reader:
                    email = row["Email"].strip().lower()
                    discord_id = row["DiscordID"].strip()
                    self.email_lookup[email] = int(discord_id)
                    self.email_tree.insert("", tk.END, values=(email, discord_id))
                    count += 1
            print(f"✅ Loaded Email Lookup from {path} ({count} entries)")
        except Exception as e:
            print(f"❌ Failed to load Email Lookup: {e}")

    def load_products_csv(self, path=None):
        if not path:
            path = fd.askopenfilename(title="Select Products CSV", filetypes=[("CSV Files", "*.csv")])
        if not path:
            return
        self.products_csv_path = path  # Save selected path
        try:
            with open(path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                self.sku_data.clear()
                self.products_tree.delete(*self.products_tree.get_children())
                count = 0
                for row in reader:
                    sku = row["SKU"].strip().upper()
                    name = row["Name"].strip()
                    url = row["URL"].strip()
                    role_id = row.get("RoleID", "").strip()
                    self.sku_data[sku] = {"name": name, "url": url, "role_id": role_id}
                    self.products_tree.insert("", tk.END, values=(sku, name, url, role_id))
                    count += 1
            print(f"✅ Loaded Products CSV from {path} ({count} entries)")
        except Exception as e:
            print(f"❌ Failed to load Products CSV: {e}")

    def sort_treeview(self, tree, col, reverse):
        """Sort treeview contents when clicking column header"""
        data = [(tree.set(k, col), k) for k in tree.get_children('')]
        # Attempt to convert to int for numeric sorting
        try:
            data.sort(key=lambda t: int(t[0]), reverse=reverse)
        except ValueError:
            data.sort(key=lambda t: t[0].lower(), reverse=reverse)
        for index, (val, k) in enumerate(data):
            tree.move(k, '', index)
        # Reverse sort next time
        tree.heading(col, command=lambda: self.sort_treeview(tree, col, not reverse))

    def filter_email_table(self, *args):
        filter_text = self.email_filter_var.get().lower()
        for item in self.email_tree.get_children():
            values = self.email_tree.item(item)['values']
            # Email column is index 0, DiscordID is index 1
            if any(filter_text in str(value).lower() for value in values):
                self.email_tree.reattach(item, '', 'end')
            else:
                self.email_tree.detach(item)

    def filter_products_table(self, *args):
        filter_text = self.products_filter_var.get().lower()
        for item in self.products_tree.get_children():
            values = self.products_tree.item(item)['values']
            # Check all columns
            if any(filter_text in str(value).lower() for value in values):
                self.products_tree.reattach(item, '', 'end')
            else:
                self.products_tree.detach(item)

    def start_bot(self):
        if self.bot_thread and self.bot_thread.is_alive():
            print("Bot is already running.")
            return

        self.bot_token = self.token_entry.get().strip()
        try:
            self.source_channel_id = int(self.source_channel_entry.get().strip())
            self.target_channel_id = int(self.target_channel_entry.get().strip())
            self.checkouts_channel_id = int(self.checkouts_channel_entry.get().strip())
            self.queue_channel_id  = int(self.queue_channel_entry.get().strip())
            self.admin_channel_id = int(self.admin_channel_entry.get().strip())
        except ValueError:
            print("One or more channel IDs are invalid. Please enter valid integers.")
            return

        if not self.bot_token:
            print("Bot token is empty. Please enter your bot token.")
            return

        # Assign global lookups so bot event handlers can access them
        global email_lookup, sku_data, recent_skus
        email_lookup = self.email_lookup
        sku_data = self.sku_data
        recent_skus = {}

        global SOURCE_CHANNEL_ID, TARGET_CHANNEL_ID, CHECKOUTS_CHANNEL_ID, QUEUE_CHANNEL_ID, STELLAR_ADMIN_CHANNEL_ID
        SOURCE_CHANNEL_ID = self.source_channel_id
        TARGET_CHANNEL_ID = self.target_channel_id
        CHECKOUTS_CHANNEL_ID = self.checkouts_channel_id
        QUEUE_CHANNEL_ID = self.queue_channel_id
        STELLAR_ADMIN_CHANNEL_ID = self.admin_channel_id

        print("Starting bot with provided configuration...")
        self.status_label.config(text="Status: Started", fg="green")

        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

    def run_bot(self):
        global bot

        intents = discord.Intents.default()
        intents.message_content = True
        bot = discord.Client(intents=intents)

        @bot.event
        async def on_ready():
            log(f"✅ Bot is online as {bot.user}")
            startup_channel = bot.get_channel(STELLAR_ADMIN_CHANNEL_ID)
            if startup_channel:
                await startup_channel.send("🚀 SKUtto is now online and ready!")
            else:
                log("⚠️ Could not find the startup channel.")

        @bot.event
        async def on_message(message):
            global sku_data, email_lookup, recent_skus

            # --- NEW: Handle queue pass embeds ---
            if message.channel.id == CHECKOUTS_CHANNEL_ID and message.embeds:
                for embed in message.embeds:
                    if (
                        "queueit" in (embed.title or "").lower()
                        or "queueit" in (embed.description or "").lower()
                    ):
                        forward_channel = bot.get_channel(QUEUE_CHANNEL_ID)
                        if forward_channel:
                            await forward_channel.send(embed=embed)
                            log("📤 Forwarded queue pass embed.")
                        try:
                            await message.delete()
                            log("🗑️ Deleted queue pass embed from checkouts.")
                        except Exception as e:
                            log(f"⚠️ Could not delete message: {e}")
                        return  # Stop further processing

            if message.channel.id == STELLAR_ADMIN_CHANNEL_ID and message.content == "$refresh":
                print("🔄 Refresh command detected, but CSV reload from GUI only currently supported.")
                await message.channel.send("⚠️ CSV reload only available via GUI currently.")
                return

            if not isinstance(message.channel, discord.TextChannel):
                return
            else:
                if message.channel.id == CHECKOUTS_CHANNEL_ID and message.embeds:
                    for embed in message.embeds:
                        is_paypal = any("paypal.com" in e.url.lower() if e.url else False for e in message.embeds)
                        log(f"📥 Received embed in checkouts channel from {'bot' if message.author.bot else 'user'}: {message.author}")
                        found = False
                        for i, embed in enumerate(message.embeds):
                            log(f"🔍 Processing embed #{i+1}")
                            for field in embed.fields:
                                if field.name.lower() in ["account", "email", "profile email"]:
                                    potential_email = field.value.strip().lower().replace("||", "")
                                    log(f"   ↪📧 Checking email: {potential_email}")
                                    if potential_email in email_lookup:
                                        user_id = email_lookup[potential_email]
                                        log(f"   ↪✅ Match found! Discord ID: {user_id}")
                                        user = await bot.fetch_user(user_id)
                                        if user:
                                            try:
                                                if is_paypal:
                                                    log(f"   ↪📦 PayPal embed detected")
                                                    await user.send(f"📦 PayPal Checkout detected for `{potential_email}`\nClick the link at the top of the message to go directly to PayPal to checkout", embed=embed)
                                                else:
                                                    await user.send("Successful Checkout!", embed=embed)
                                                log(f"   {potential_email} - ✉️ Embed forwarded to user: {user}")
                                            except discord.Forbidden:
                                                log(f"   🚫 Cannot DM user {user} — DMs likely disabled.")
                                            found = True
                                            break
                            if found:
                                break

            if message.channel.id != SOURCE_CHANNEL_ID or not message.author.bot:
                return

            content = message.content or ""
            if not content and message.embeds:
                parts = []
                for embed in message.embeds:
                    if embed.title:
                        parts.append(embed.title)
                    if embed.description:
                        parts.append(embed.description)
                    for field in embed.fields:
                        parts.append(field.name)
                        parts.append(field.value)
                content = "\n".join(parts)
                log("\n|--------------------------------|\n")

            platform = None
            keyword = None
            lower_content = content.lower()
            for key, (plat, kw) in platform_map.items():
                if key in lower_content:
                    platform = key
                    keyword = kw
                    break
            else:
                return

            lines = content.splitlines()
            sku = None
            for i, line in enumerate(lines):
                if line.strip().lower() == keyword and i + 1 < len(lines):
                    sku = lines[i + 1].strip().upper()
                    break

            if not sku:
                return
                return
            from datetime import timezone
            now = datetime.datetime.now(timezone.utc)
            if sku in recent_skus and (now - recent_skus[sku]).total_seconds() < DUPLICATE_TIMEOUT:
                log(f"⏳ Skipping duplicate: {sku}")
                log("\n|--------------------------------|\n")
                return

            recent_skus[sku] = now

            product = sku_data.get(sku)    
            output_channel = bot.get_channel(TARGET_CHANNEL_ID)
            if not output_channel:
                log("⚠️ Target channel not found.")
                log("\n|--------------------------------|\n")
                return

            if product:
                log(f"✅ **{product['name']}**\n🔗 {product['url']}")
            else:
                if platform == "costco":
                    await output_channel.send(f"✅ Costco Restock - **{sku}**")
                else:
                    await output_channel.send(f"❌ No info found for SKU `{sku}`.")

            if message.embeds:
                modified_embeds = []

                for embed in message.embeds:
                    # Clone as a dict
                    embed_dict = embed.to_dict()

                    # Clean up fields
                    cleaned_fields = []
                    for field in embed_dict.get("fields", []):
                        if field["name"].strip().lower() == "proxy":
                            continue  # Skip proxy field
                        cleaned_fields.append({
                            "name": field["name"].replace("||", ""),
                            "value": field["value"].replace("||", ""),
                            "inline": field.get("inline", True)
                        })
                    embed_dict["fields"] = cleaned_fields

                    # Update title and url if product is known
                    if product:
                        embed_dict["title"] = f"{platform.capitalize()} Restock - {product['name']}"
                        embed_dict["url"] = product["url"]

                    # Build cleaned embed
                    try:
                        new_embed = discord.Embed.from_dict(embed_dict)
                        modified_embeds.append(new_embed)
                    except Exception as e:
                        log(f"⚠️ Failed to build cleaned embed: {e}")

                # Send role ping if available
                mention = ""
                if product and product.get("role_id"):
                    role_id = product["role_id"]
                    if role_id.isdigit():
                        mention = f"<@&{role_id}> - {platform.capitalize()} Restock - {product['name']}"

                if mention:
                    await output_channel.send(content=mention)
                if modified_embeds:
                    if platform == "queueit":
                        output_channel = bot.get_channel(QUEUE_CHANNEL_ID)
                        await output_channel.send(embeds=modified_embeds)
                    else:
                        await output_channel.send(embeds=modified_embeds)

                
            elif message.content:
                mention = ""
                if product and product.get("role_id"):
                    role_id = product["role_id"]
                    if role_id.isdigit():
                        mention = f"<@&{role_id}>"
                if mention:
                    await output_channel.send(content=mention)
                await output_channel.send(content=message.content)

        self.bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.bot_loop)
        try:
            self.bot_loop.run_until_complete(bot.start(self.bot_token))
        except Exception as e:
            print(f"Bot stopped with error: {e}")
        finally:
            self.bot_loop.run_until_complete(bot.close())
            self.bot_loop.close()
            self.root.after(0, self.on_bot_stopped)

    def stop_bot(self):
        if self.bot_loop and self.bot_loop.is_running():
            print("Stopping bot...")
            asyncio.run_coroutine_threadsafe(bot.close(), self.bot_loop)
            self.status_label.config(text="Status: Stopping...", fg="orange")
            self.stop_button.config(state=tk.DISABLED)
        else:
            print("Bot is not running.")

    def on_bot_stopped(self):
        print("Bot stopped.")
        self.status_label.config(text="Status: Offline", fg="red")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)


def main():
    root = tk.Tk()
    gui = DiscordBotGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
