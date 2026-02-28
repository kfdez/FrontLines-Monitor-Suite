"""Skutto-specific bot event handlers."""
import discord
import datetime
from datetime import timezone
from typing import Any


# Platform mapping
PLATFORM_MAP = {
    "walmart": ("walmart", "product"),
    "gamestop": ("gamestop", "product"),
    "amazon": ("amazonv3", "sku"),
    "costco": ("costco", "title/sku"),
    "bestbuy": ("bestbuy", "title/sku"),
    "popmart": ("popmart", "title/sku"),
    "queueit": ("queueit", "Queue Pass"),
    "indigo": ("indigoca", "product"),
}

DUPLICATE_TIMEOUT = 500  # seconds


class SkuttoBotEvents:
    """Handles bot events for the Skutto module."""

    def __init__(self, app):
        self.app = app
        self.recent_skus = {}

    def log(self, message: str):
        """Log a message to the application's log panel."""
        if hasattr(self.app, 'log_message'):
            self.app.log_message(message)
        print(message)

    async def on_ready(self, bot):
        """Called when bot is ready."""
        self.log(f"✅ SKUtto bot is online as {bot.user}")

        # Get admin channel from config
        admin_channel_id = self.app.bot.admin_channel_id
        if admin_channel_id:
            admin_channel = bot.get_channel(admin_channel_id)
            if admin_channel:
                await admin_channel.send("🚀 SKUtto is now online and ready!")
            else:
                self.log("⚠️ Could not find admin channel.")

    async def on_message(self, message: discord.Message, bot):
        """Handle incoming messages for SKU monitoring."""
        # Handle checkouts channel for email lookup
        if message.channel.id == self.app.bot.checkouts_channel_id and message.embeds:
            await self._handle_checkouts(message, bot)

        # Only process source channel for SKU monitoring
        if not message.author.bot:
            return

        if message.channel.id != self.app.bot.source_channel_id:
            return

        await self._process_sku_message(message, bot)

    async def _handle_checkouts(self, message: discord.Message, bot):
        """Forward checkout info to users based on email lookup."""
        email_lookup = self.app.bot.email_lookup

        for embed in message.embeds:
            is_paypal = any(
                "paypal.com" in (e.url or "").lower()
                for e in message.embeds
                if e.url
            )

            self.log(f"📥 Checkout embed received from {message.author}")

            found = False
            for field in embed.fields:
                if field.name.lower() in ["account", "email", "profile email"]:
                    potential_email = field.value.strip().lower().replace("||", "")
                    self.log(f"   Checking email: {potential_email}")

                    if potential_email in email_lookup:
                        user_id = email_lookup[potential_email]
                        self.log(f"   ✅ Match found for {potential_email} -> Discord ID: {user_id}")

                        try:
                            user = await bot.fetch_user(user_id)
                            if user:
                                if is_paypal:
                                    await user.send(
                                        f"📦 PayPal Checkout detected for `{potential_email}`\n"
                                        "Click the link at the top of the message to go directly to PayPal",
                                        embed=embed
                                    )
                                else:
                                    await user.send("Successful Checkout!", embed=embed)
                                self.log(f"   ✉️ Checkout forwarded to user {user_id}")
                        except discord.Forbidden:
                            self.log(f"   🚫 Cannot DM user {user_id} — DMs likely disabled.")
                        found = True
                        break

            if found:
                break

    async def _process_sku_message(self, message: discord.Message, bot):
        """Process SKU messages from source channel."""
        content = message.content or ""

        # Extract content from embeds if no text content
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
            self.log("-" * 30)

        # Detect platform
        platform = None
        keyword = None
        lower_content = content.lower()
        for key, (plat, kw) in PLATFORM_MAP.items():
            if key in lower_content:
                platform = key
                keyword = kw
                break
        else:
            return

        # Extract SKU
        lines = content.splitlines()
        sku = None
        for i, line in enumerate(lines):
            if line.strip().lower() == keyword and i + 1 < len(lines):
                sku = lines[i + 1].strip().upper()
                break

        if not sku:
            return

        # Check for duplicates
        now = datetime.datetime.now(timezone.utc)
        if sku in self.recent_skus:
            time_diff = (now - self.recent_skus[sku]).total_seconds()
            if time_diff < DUPLICATE_TIMEOUT:
                self.log(f"⏳ Skipping duplicate: {sku}")
                return

        self.recent_skus[sku] = now

        # Look up product - check SKU and SKU2
        product = self.app.bot.sku_data.get(sku)
        if not product:
            # Check SKU2
            for prod in self.app.bot.sku_data.values():
                if prod.get('sku2', '').upper() == sku:
                    product = prod
                    break

        output_channel = bot.get_channel(self.app.bot.target_channel_id)

        if not output_channel:
            self.log("⚠️ Target channel not found.")
            return

        if product:
            self.log(f"✅ Forwarding: {product['name']} ({sku})")
        else:
            if platform == "costco":
                await output_channel.send(f"✅ Costco Restock - **{sku}**")
                self.log(f"⚠️ No product data for {sku}, posted as unknown Costco")
            else:
                await output_channel.send(f"❌ No info found for SKU `{sku}`.")
                self.log(f"⚠️ No product data for {sku}")

        # Handle embeds
        if message.embeds:
            modified_embeds = []

            for embed in message.embeds:
                embed_dict = embed.to_dict()

                # Clean up fields - remove proxy
                cleaned_fields = []
                for field in embed_dict.get("fields", []):
                    if field["name"].strip().lower() == "proxy":
                        continue
                    cleaned_fields.append({
                        "name": field["name"].replace("||", ""),
                        "value": field["value"].replace("||", ""),
                        "inline": field.get("inline", True)
                    })
                embed_dict["fields"] = cleaned_fields

                # Update title and url if product known
                if product:
                    embed_dict["title"] = f"{platform.capitalize()} Restock - {product['name']}"
                    embed_dict["url"] = product.get("url", "")

                try:
                    new_embed = discord.Embed.from_dict(embed_dict)
                    modified_embeds.append(new_embed)
                except Exception as e:
                    self.log(f"⚠️ Failed to build cleaned embed: {e}")

            # Send role ping if available
            mention = ""
            if product and product.get("role_id"):
                role_id = product["role_id"]
                if role_id.isdigit():
                    mention = f"<@&{role_id}> - {platform.capitalize()} Restock - {product['name']}"

            if mention:
                await output_channel.send(content=mention)

            if modified_embeds:
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
