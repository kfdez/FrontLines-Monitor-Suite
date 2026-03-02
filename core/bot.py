"""Discord bot handler for the application."""
import asyncio
import discord
from typing import Optional, Dict, Any, Callable
from core.database import Database


class DiscordBot:
    def __init__(self, token: str, db: Database):
        self.token = token
        self.db = db
        self.bot: Optional[discord.Client] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._is_running = False

        # Callbacks for events
        self.on_ready_callback: Optional[Callable] = None
        self.on_message_callback: Optional[Callable] = None
        self.on_email_changed_callback: Optional[Callable] = None

        # Configuration set by GUI
        self.source_channel_id: Optional[int] = None
        self.target_channel_id: Optional[int] = None
        self.checkouts_channel_id: Optional[int] = None
        self.admin_channel_id: Optional[int] = None
        self.enable_ping: bool = False

        # Data placeholders
        self.email_lookup: Dict[str, int] = {}
        self.sku_data: Dict[str, Dict[str, Any]] = {}
        self.recent_skus: Dict[str, Any] = {}

    def set_config(
        self,
        source_channel_id: int,
        target_channel_id: int,
        checkouts_channel_id: int,
        admin_channel_id: int
    ):
        """Set channel configuration."""
        self.source_channel_id = source_channel_id
        self.target_channel_id = target_channel_id
        self.checkouts_channel_id = checkouts_channel_id
        self.admin_channel_id = admin_channel_id

    def refresh_data(self):
        """Refresh email lookup and SKU data from database."""
        self.email_lookup = self.db.get_email_lookup_dict()
        # SKU data loaded separately from sheets

    def set_sku_data(self, sku_data: Dict[str, Dict[str, Any]]):
        """Set SKU data from sheets."""
        self.sku_data = sku_data

    def set_on_ready(self, callback: Callable):
        """Set the on_ready callback."""
        self.on_ready_callback = callback

    def set_on_message(self, callback: Callable):
        """Set the on_message callback."""
        self.on_message_callback = callback

    def set_on_email_changed(self, callback: Callable):
        """Set callback for email changes."""
        self.on_email_changed_callback = callback

    async def _handle_commands(self, message: discord.Message) -> bool:
        """Handle bot commands. Returns True if command was handled."""
        print(f"DEBUG _handle_commands: channel={message.channel}, type={type(message.channel)}")
        if not message.content.startswith('!'):
            return False

        content = message.content[1:].strip()
        parts = content.split()
        if not parts:
            return False

        command = parts[0].lower()
        args = parts[1:]
        print(f"DEBUG: processing command '{command}'")

        # !help - works in DMs
        if command == 'help':
            embed = discord.Embed(
                title="📋 Available Commands",
                description="**SKU Submission:**\n"
                           "• `!addsku <sku> <name> [url]` - Submit a new SKU\n"
                           "Example: `!addsku NSW-LITE-BLU Nintendo Switch Lite Blue`\n\n"
                           "**Emails:**\n"
                           "• `!addemail <email>` - Link an email\n"
                           "• `!removeemail <email>` - Remove an email\n"
                           "• `!lemails` - List your emails",
                color=discord.Color.blue()
            )
            await message.channel.send(embed=embed)
            return True

        # !lemails - list emails
        if command == 'lemails':
            discord_id = message.author.id
            emails = self.db.get_emails_by_discord_id(discord_id)

            if emails:
                email_list = "\n".join([f"- {e['email']}" for e in emails])
                embed = discord.Embed(
                    title="📧 Your Linked Emails",
                    description=email_list,
                    color=discord.Color.blue()
                )
            else:
                embed = discord.Embed(
                    description="You have no emails linked. Use `!addemail <email>` to add one.",
                    color=discord.Color.red()
                )
            await message.channel.send(embed=embed)
            return True

        # !addemail <email>
        if command == 'addemail':
            if len(args) < 1:
                embed = discord.Embed(description="Usage: `!addemail <email>`", color=discord.Color.red())
                await message.channel.send(embed=embed)
                return True

            email = args[0]
            discord_id = message.author.id

            if self.db.email_exists(email):
                embed = discord.Embed(
                    description=f"❌ Email `{email}` is already linked to another account.",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)
                return True

            success = self.db.add_email(email, discord_id)
            if success:
                embed = discord.Embed(
                    description=f"✅ Email `{email}` linked to your account!",
                    color=discord.Color.green()
                )
                # Refresh email lookup and notify GUI
                self.refresh_data()
                if self.on_email_changed_callback:
                    await self.on_email_changed_callback()
            else:
                embed = discord.Embed(description="❌ Failed to add email.", color=discord.Color.red())
            await message.channel.send(embed=embed)
            return True

        # !removeemail <email>
        if command == 'removeemail':
            if len(args) < 1:
                embed = discord.Embed(description="Usage: `!removeemail <email>`", color=discord.Color.red())
                await message.channel.send(embed=embed)
                return True

            email = args[0]
            discord_id = message.author.id

            success = self.db.remove_email(email, discord_id)
            if success:
                embed = discord.Embed(
                    description=f"✅ Email `{email}` removed from your account!",
                    color=discord.Color.green()
                )
                # Refresh email lookup and notify GUI
                self.refresh_data()
                if self.on_email_changed_callback:
                    await self.on_email_changed_callback()
            else:
                embed = discord.Embed(
                    description="❌ Email not found or not linked to your account.",
                    color=discord.Color.red()
                )
            await message.channel.send(embed=embed)
            return True

        # !addsku <sku> <name> [url]
        elif command == 'addsku':
            if len(args) < 2:
                embed = discord.Embed(description="Usage: `!addsku <sku> <name> [url]`", color=discord.Color.red())
                await message.channel.send(embed=embed)
                return True

            sku = args[0]
            name = " ".join(args[1:-1]) if len(args) > 2 else args[1]
            url = args[-1] if len(args) > 2 else ""

            # Determine platform from URL
            platform = "unknown"
            url_lower = url.lower()
            if "walmart" in url_lower:
                platform = "walmart"
            elif "gamestop" in url_lower:
                platform = "gamestop"
            elif "amazon" in url_lower:
                platform = "amazon"
            elif "costco" in url_lower:
                platform = "costco"
            elif "bestbuy" in url_lower:
                platform = "bestbuy"
            elif "popmart" in url_lower:
                platform = "popmart"
            elif "queueit" in url_lower or "queue" in url_lower:
                platform = "queueit"

            sku_id = self.db.add_pending_sku(
                sku=sku,
                name=name,
                url=url,
                platform=platform,
                submitted_by=message.author.id
            )

            embed = discord.Embed(
                description=f"✅ SKU `{sku}` submitted for approval!\nAn admin will review your submission shortly.",
                color=discord.Color.green()
            )
            await message.channel.send(embed=embed)

            return True

        return False

    def start(self, callback: Optional[Callable] = None):
        """Start the bot in a separate thread."""
        import threading

        def run():
            asyncio.set_event_loop(asyncio.new_event_loop())
            self.loop = asyncio.get_event_loop()
            self.loop.run_until_complete(self._run_bot())

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    async def _run_bot(self):
        """Run the bot with message commands (DMs only)."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        intents.messages = True

        class MessageBot(discord.Client):
            def __init__(self, intents, bot_instance):
                super().__init__(intents=intents)
                self.bot_instance = bot_instance

            async def on_ready(self):
                print(f"✅ Logged in as {self.user}")
                print(f"📍 Source channel: {self.bot_instance.source_channel_id}")
                print(f"📍 Target channel: {self.bot_instance.target_channel_id}")
                self.bot_instance._is_running = True
                if self.bot_instance.on_ready_callback:
                    await self.bot_instance.on_ready_callback(self.bot_instance)

            async def on_message(self, message):
                # Handle commands only in DMs
                if isinstance(message.channel, discord.DMChannel):
                    if not message.author.bot:
                        await self.bot_instance._handle_commands(message)
                else:
                    # For server channels, forward to monitoring callback
                    if self.bot_instance.on_message_callback:
                        try:
                            await self.bot_instance.on_message_callback(message, self.bot_instance)
                        except Exception as e:
                            print(f"Error in message callback: {e}")

        self.bot = MessageBot(intents, self)

        try:
            await self.bot.start(self.token)
        except Exception as e:
            print(f"Bot stopped: {e}")
        finally:
            self._is_running = False

    async def stop(self):
        """Stop the bot."""
        if self.bot:
            await self.bot.close()
            self._is_running = False

    def stop_sync(self):
        """Stop the bot from another thread."""
        import traceback
        import asyncio
        try:
            # Try thread-safe stop first
            if self.loop and self.loop.is_running():
                future = asyncio.run_coroutine_threadsafe(self.stop(), self.loop)
                try:
                    # Wait up to 10 seconds for bot to stop
                    future.result(timeout=10)
                    print("Bot stopped gracefully")
                except TimeoutError:
                    print("Bot stop timed out, forcing close")
                    self._is_running = False
                except Exception as e:
                    print(f"Error waiting for bot stop: {e}")
                    self._is_running = False
            else:
                # Loop not running or not available
                if self.bot:
                    try:
                        asyncio.run(self.stop())
                    except RuntimeError as e:
                        # Event loop already closed or closing
                        print(f"Event loop closing: {e}")
                        self._is_running = False
        except Exception as e:
            print(f"Error in stop_sync: {e}")
            print(traceback.format_exc())

    def is_running(self) -> bool:
        """Check if bot is running."""
        return self._is_running

    async def send_message(self, channel_id: int, content: str = None, embed=None):
        """Send a message to a channel."""
        if self.bot:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(content=content, embed=embed)

    async def DM_user(self, user_id: int, content: str = None, embed=None):
        """Send a DM to a user."""
        if self.bot:
            try:
                user = await self.bot.fetch_user(user_id)
                if user:
                    await user.send(content=content, embed=embed)
            except discord.Forbidden:
                print(f"Cannot DM user {user_id}")
