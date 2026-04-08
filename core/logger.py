"""Application-wide error logging to a rotating log file."""
import logging
import logging.handlers
import os
import sys
import threading


def get_log_path() -> str:
    """Return the appropriate error.log path for installed vs dev environments."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller exe — log alongside the executable
        base = os.path.dirname(sys.executable)
    else:
        # Running from source — log in the project root
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "error.log")


def setup_logging() -> str:
    """
    Set up file-based error logging for the entire application.

    Hooks into:
      - Python's logging system (any logger that calls .error/.exception/.critical)
      - sys.excepthook     — uncaught exceptions on the main thread
      - threading.excepthook — uncaught exceptions on background threads
      - asyncio loop handler — set separately via get_asyncio_exception_handler()

    Returns the path to the log file.
    """
    log_path = get_log_path()

    # Rotating handler: max 5 MB per file, keep 3 backups
    handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setLevel(logging.ERROR)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    root_logger.addHandler(handler)

    # ── Main-thread uncaught exceptions ──────────────────────────────────────
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger("uncaught").error(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = handle_exception

    # ── Background-thread uncaught exceptions (Python 3.8+) ──────────────────
    def handle_thread_exception(args):
        if args.exc_type is SystemExit:
            return
        logging.getLogger("thread").error(
            "Uncaught exception in thread '%s'",
            args.thread.name if args.thread else "unknown",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = handle_thread_exception

    return log_path


def get_asyncio_exception_handler():
    """
    Return an asyncio loop exception handler that writes to the error log.

    Usage in an asyncio context:
        loop.set_exception_handler(get_asyncio_exception_handler())
    """
    def handler(loop, context):
        exception = context.get("exception")
        message = context.get("message", "No message")
        if exception:
            logging.getLogger("asyncio").error(
                "Asyncio exception: %s", message,
                exc_info=exception,
            )
        else:
            logging.getLogger("asyncio").error(
                "Asyncio error: %s — context: %s", message, context,
            )

    return handler
