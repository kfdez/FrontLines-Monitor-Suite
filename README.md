# FrontLines Monitor Suite (SKUtto 3.0)

A Discord bot monitoring application with a Tkinter GUI. Monitors source Discord channels for product restock embeds, matches them against a product database stored in Google Sheets, transforms the embeds (adding role pings, modifying titles/footers), and forwards them to a target channel.

## Features

- **Tkinter GUI** - Easy configuration with Products, Emails, and Settings tabs
- **Discord Slash Commands** - `/help`, `/addsku`, `/addemail`, `/removeemail`, `/lemails`
- **SKU Monitoring** - Monitors Discord channels for restock embeds and forwards matching products
- **Role Pings** - Automatically pings Discord roles for matched products
- **Email Management** - Link emails to Discord users for checkout notifications
- **Google Sheets Integration** - Product database stored in Google Sheets

## Setup

1. Install dependencies:
```bash
pip install discord google-api-python-client google-auth-oauthlib
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

Or run directly:
```bash
python skutto3.0.pyw
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

Users can interact via slash commands in DMs:
- `/help` - Show available commands
- `/addsku <sku> <name> [url]` - Submit a new SKU
- `/addemail <email>` - Link an email to your account
- `/removeemail <email>` - Remove an email
- `/lemails` - List your linked emails

## Project Structure

- `gui/` - Tkinter GUI application
- `core/` - Bot, database, and sheets integration
- `modules/skutto/` - Skutto-specific event handlers
