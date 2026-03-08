# FrontLines Monitor Suite (SKUtto 3.0)

A Discord bot monitoring application with a Tkinter GUI. Monitors source Discord channels for product restock embeds, matches them against a product database stored in Google Sheets, transforms the embeds (adding role pings, modifying titles/footers), and forwards them to a target channel.

## Features

- **Tkinter GUI** - Easy configuration with sidebar navigation and multiple monitoring modules
- **SKUtto** - Discord embed monitoring for product restocks with SKU matching
- **Hobbiesville (HV Monitor)** - Shopify product monitoring via GraphQL API with stock alerts
- **Shopify Monitor** - Multi-store Shopify scraping with keyword matching and Discord webhooks
- **Proxies** - Proxy management for HTTP requests
- **Discord Slash Commands** - `/help`, `/addsku`, `/addemail`, `/removeemail`, `/lemails`
- **Role Pings** - Automatically pings Discord roles for matched products
- **Email Management** - Link emails to Discord users for checkout notifications
- **Google Sheets Integration** - Product database stored in Google Sheets

## Modules

### SKUtto
Monitors Discord channels for restock embeds and forwards matching products based on SKU/SKU2/Name matching.

### Hobbiesville (HV Monitor)
Monitors Shopify products via GraphQL API and sends Discord webhooks when items come back in stock.

**Configuration:**
- Store GraphQL URL (e.g., `https://yourstore.myshopify.com/api/2024-07/graphql.json`)
- Storefront Access Token
- Discord Webhook URL
- Role ID for pings
- Check interval (10-300 seconds)
- Auto-start option

**Products:**
Add product IDs in the format `gid://shopify/Product/123456789` (one per line). Add `|ping` suffix for per-product ping override.

### Shopify Monitor
Monitors multiple Shopify stores for products matching configured keywords and sends Discord webhooks on new/in-stock items.

**Configuration:**
- Main Webhook URL (for all products)
- Singles Webhook URL (separate for card singles)
- Ignore Singles option
- Check interval (30-3600 seconds)
- Max pages per store
- Max concurrent workers
- Auto-start option

**Stores & Keywords:**
Configure store domains and keywords to match against product titles, tags, and types.

### Proxies
Manage HTTP proxies for monitoring modules. Format: `host:port:username:password` (one per line).

## Setup

1. Install dependencies:
```bash
pip install discord google-api-python-client google-auth-oauthlib requests
```

2. Configure the bot:
   - Go to Discord Developer Portal and create a bot
   - Enable **Message Content** and **Direct Messages** intents
   - Invite the bot with `bot` and `applications.commands` scopes

3. Configure credentials:
   - Add your bot token in the Settings tab
   - Add Google Sheets credentials (`credentials.json`)
   - Set source channel (to monitor) and target channel (to forward embeds)

## Running

```bash
python main.py
```

## Google Sheets Format

Products should be stored with these columns (in order):
- SKU
- SKU2
- Name
- URL
- Platform
- RoleID
- Role

## Bot Commands

Users can interact via commands in DMs (prefix with `!`):
- `!help` - Show available commands
- `!addsku <sku> <name> [url]` - Submit a new SKU
- `!addemail <email>` - Link an email to your account
- `!removeemail <email>` - Remove an email
- `!lemails` - List your linked emails

## Project Structure

- `gui/` - Tkinter GUI application
  - `gui/app.py` - Main application with sidebar navigation
  - `gui/tabs/` - Tab components (Products, Emails, Settings, HV Monitor, Proxies)
- `core/` - Core functionality
  - `core/bot.py` - Discord bot
  - `core/database.py` - SQLite database
  - `core/sheets.py` - Google Sheets integration
  - `core/hv_monitor.py` - HV Monitor backend
- `hv_monitor_data/` - HV Monitor data storage
- `modules/skutto/` - Skutto-specific event handlers
