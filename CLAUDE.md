# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SKUtto 3.0 is a Discord bot monitoring application with a Tkinter GUI. It monitors source Discord channels for product restock embeds, matches them against a product database, transforms the embeds (adding role pings, modifying titles/footers), and forwards them to a target channel.

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

- **gui/app.py**: Main Tkinter application window with header (start/stop buttons, status indicator), tabbed content area, and activity log panel
- **gui/tabs/**: Tabbed interface with Products, Emails, and Settings tabs
- **core/bot.py**: Discord bot wrapper that runs in a separate thread with its own asyncio event loop
- **core/database.py**: SQLite database interface for storing configuration, products, emails, pending SKUs
- **core/sheets.py**: Google Sheets integration for importing product data

### Data Flow

1. Products are imported from Google Sheets (ProductsTab → SheetsManager)
2. Bot monitors source channel for embeds
3. When embed received, `_handle_message` in gui/app.py processes it
4. `_process_embed` matches SKU against product database and transforms the embed
5. Transformed embed is sent to target channel with optional role ping

### Key Classes

- **DiscordBot** (core/bot.py): Manages Discord client with slash commands, runs in daemon thread with its own asyncio event loop
- **MainApplication** (gui/app.py): Tkinter main window, owns DiscordBot instance, handles UI events
- **Database** (core/database.py): SQLite CRUD operations
- **ProductsTab** (gui/tabs/products_tab.py): Product management grid - column order is SKU, SKU2, Name, URL, Platform, RoleID, Role

### Important Implementation Notes

- Bot runs in a separate thread with its own asyncio event loop using `discord.ext.commands.Bot`
- Slash commands require the `applications.commands` scope when inviting the bot
- Message handling callbacks must be async and use `root.after()` for GUI updates
- Products use SKU matching: checks SKU, SKU2, or Name columns for matches
- Role pings come from product's RoleID column (not a global setting)
- Embed transformation: removes "proxy" and "offer id" fields, updates title to `[Platform] Restock - Item Name`, sets footer to "SKUtto 3.0"
- Google Sheets column order: SKU, SKU2, Name, URL, Platform, RoleID, Role (must match for proper read/write)

## Bot Commands

The bot uses **Discord slash commands** (not message commands). Users interact via `/` commands:

- `/help` - Show available commands
- `/addsku <sku> <name> [url]` - Submit a new SKU for approval
- `/addemail <email>` - Link an email to your account
- `/removeemail <email>` - Remove an email from your account
- `/lemails` - List your linked emails

Note: Commands only work in DMs, not in server channels.

## Configuration

Configuration is stored in the SQLite database (`skutto.db`) in the `config` table. Key settings:
- `bot_token` - Discord bot token
- `source_channel_id` - Channel to monitor for restock embeds
- `target_channel_id` - Channel to forward transformed embeds to
- `checkouts_channel_id` - Optional channel for checkout notifications
- `admin_channel_id` - Channel for SKU submission notifications (no longer used actively)
- `enable_ping` - Whether to ping roles on restocks
- `google_sheets_id` - Google Sheets spreadsheet ID for products

## Dependencies

- `discord.py` - Discord bot API
- `google-api-python-client` - Google Sheets API
- `google-auth-oauthlib` - Google authentication
- `tkinter` - GUI (built into Python)
- `sqlite3` - Database (built into Python)
