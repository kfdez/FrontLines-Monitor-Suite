# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SKUtto 3.0 is a Discord bot monitoring application with a Tkinter GUI. It monitors source Discord channels for product restock embeds, matches them against a product database, transforms the embeds (adding role pings, modifying titles/footers), and forwards them to a target channel.

The application has multiple monitoring modules:
- **SKUtto**: Discord embed monitoring for product restocks
- **Hobbiesville (HV Monitor)**: Shopify product monitoring via GraphQL API
- **Proxies**: Proxy management for HTTP requests

## Running the Application

```bash
python main.py
```

## Git Commands

```bash
git add .                    # Stage all changes
git commit -m "message"     # Commit changes
git push                    # Push to remote
git pull                    # Pull from remote
git status                  # Show working tree status
```

## Architecture

### Core Components

- **gui/app.py**: Main Tkinter application with sidebar navigation, header controls (start/stop buttons, status indicator), tabbed content area, and activity log panel
- **gui/tabs/**: Tabbed interface - ProductsTab, EmailsTab, SettingsTab, HVMonitorTab, ProxiesTab
- **core/bot.py**: Discord bot wrapper running in a separate thread with its own asyncio event loop
- **core/database.py**: SQLite database interface for config, products, emails, pending SKUs
- **core/sheets.py**: Google Sheets integration for importing product data
- **core/hv_monitor.py**: HV Monitor backend for Shopify GraphQL API polling

### Views (Sidebar Navigation)

The app uses a sidebar with collapsible navigation:
- **SKUtto**: Discord bot monitoring (default view)
- **Hobbiesville**: Shopify product monitor
- **Proxies**: Proxy management
- **Shopify Monitor**: Placeholder for future module

### Data Flow (SKUtto)

1. Products imported from Google Sheets (ProductsTab → SheetsManager)
2. Bot monitors source channel for embeds
3. `_handle_message` in gui/app.py processes received embeds
4. `_process_embed` matches SKU against product database and transforms the embed
5. Transformed embed sent to target channel with optional role ping

### Key Classes

- **DiscordBot** (core/bot.py): Manages Discord client with slash commands, runs in daemon thread with its own asyncio event loop
- **MainApplication** (gui/app.py): Tkinter main window, owns DiscordBot and HVMonitor instances, handles UI events
- **Database** (core/database.py): SQLite CRUD operations
- **HVMonitor** (core/hv_monitor.py): Shopify GraphQL polling, stock tracking, Discord webhook notifications
- **ProductsTab** (gui/tabs/products_tab.py): Product management - columns: SKU, SKU2, Name, URL, Platform, RoleID, Role

### Important Implementation Notes

- Bot runs in separate thread with own asyncio event loop using `discord.ext.commands.Bot`
- Modules (HV Monitor) run in daemon threads, use callbacks for UI updates
- Message handling callbacks must be async and use `root.after()` for GUI updates
- Products use SKU matching: checks SKU, SKU2, or Name columns
- Role pings come from product's RoleID column (not global setting)
- Embed transformation: removes "proxy"/"offer id" fields, updates title to `[Platform] Restock - Item Name`, sets footer to "SKUtto 3.0"
- Google Sheets column order: SKU, SKU2, Name, URL, Platform, RoleID, Role

## Bot Commands (SKUtto)

Discord slash commands (not message commands). Works in DMs only:

- `/help` - Show available commands
- `/addsku <sku> <name> [url]` - Submit new SKU for approval
- `/addemail <email>` - Link email to your account
- `/removeemail <email]` - Remove email from your account
- `/lemails` - List your linked emails

## HV Monitor (Hobbiesville)

Monitors Shopify products via GraphQL API and sends Discord webhooks on stock changes.

### Configuration (stored in SQLite `config` table)
- `hv_store_url` - Shopify GraphQL endpoint
- `hv_token` - Storefront access token
- `hv_webhook` - Discord webhook URL
- `hv_role_id` - Role ID for pings
- `hv_ping_enabled` - Global ping toggle
- `hv_check_interval` - Polling interval (default 30s)
- `hv_auto_start` - Auto-start on app launch

### Products
- Stored in `hv_monitor_data/products.txt` (one per line, `|ping` suffix for ping-enabled)
- Stock status persisted in `hv_monitor_data/stock_status.json`
- Metadata cached in `hv_monitor_data/metadata.json`

### Proxy Support
- Proxies stored in database `proxies` config key
- Format: `host:port:username:password` (one per line)
- HV Monitor uses random proxy from list for each request

## Configuration

Settings stored in SQLite database (`skutto.db`) `config` table:

| Key | Description |
|-----|-------------|
| bot_token | Discord bot token |
| source_channel_id | Channel to monitor for embeds |
| target_channel_id | Channel to forward transformed embeds |
| checkouts_channel_id | Channel for checkout notifications |
| enable_ping | Whether to ping roles on restocks |
| google_sheets_id | Google Sheets spreadsheet ID |
| hv_* | HV Monitor settings (see above) |
| proxies | Proxy list (one per line) |

## Dependencies

- `discord.py` - Discord bot API
- `google-api-python-client` - Google Sheets API
- `google-auth-oauthlib` - Google authentication
- `requests` - HTTP library for GraphQL/proxy requests
- `tkinter` - GUI (built into Python)
- `sqlite3` - Database (built into Python)
