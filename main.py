"""Main entry point for SKUtto 3.0."""
import sys
import os

# Add current directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.logger import setup_logging
log_path = setup_logging()
print(f"Error logging active → {log_path}")

from gui.app import MainApplication
import tkinter as tk


def main():
    """Main entry point."""
    root = tk.Tk()
    app = MainApplication(root)
    root.mainloop()


if __name__ == "__main__":
    main()
