"""Main entry point for FrontLines Monitor Suite."""
import threading
import time
from src.web import app
from src.config import config


def run_flask():
    """Run Flask web server."""
    print(f"Starting web dashboard on {config.web_host}:{config.web_port}")
    app.run(host=config.web_host, port=config.web_port, debug=False, use_reloader=False)


def main():
    """Main entry point."""
    print("=" * 50)
    print("FrontLines Monitor Suite")
    print("=" * 50)

    # Start web server
    web_thread = threading.Thread(target=run_flask, daemon=True)
    web_thread.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
