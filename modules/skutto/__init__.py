"""Skutto module initialization."""
from modules.skutto.bot_events import SkuttoBotEvents
from modules.skutto.config import SkuttoConfig


class SkuttoModule:
    """Main module loader for Skutto."""

    name = "skutto"
    version = "3.0"

    def __init__(self, app):
        self.app = app
        self.config = SkuttoConfig()
        self.bot_events = SkuttoBotEvents(app)

    def load(self):
        """Load the module."""
        print(f"Loading {self.name} v{self.version}...")

        # Set up bot events
        if hasattr(self.app, 'bot'):
            self.app.bot.set_on_ready(self.bot_events.on_ready)
            self.app.bot.set_on_message(self.bot_events.on_message)

        print(f"{self.name} module loaded.")

    def unload(self):
        """Unload the module."""
        print(f"Unloading {self.name} module...")
        print(f"{self.name} module unloaded.")


# Module loader interface
def load_module(app):
    """Load the Skutto module."""
    module = SkuttoModule(app)
    module.load()
    return module
