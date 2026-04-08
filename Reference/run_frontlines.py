#!/usr/bin/env python3
"""
FrontLines Monitoring Suite 2.0

Main entry point script. Run this to start the application.

Usage:
    python run_frontlines.py
"""

import sys
from pathlib import Path

# Ensure the frontlines package is importable
script_dir = Path(__file__).parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))


def main():
    """Launch the FrontLines application."""
    try:
        from frontlines.launcher.app import main as app_main
        app_main()
    except ImportError as e:
        print(f"Import error: {e}")
        print("\nMake sure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
