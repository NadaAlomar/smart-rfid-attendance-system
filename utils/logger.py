"""Central logging configuration. Writes rotating logs under data/."""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
os.makedirs(_LOG_DIR, exist_ok=True)

_ERROR_LOG = os.path.join(_LOG_DIR, "errors.log")
_APP_LOG = os.path.join(_LOG_DIR, "app.log")
_SCAN_LOG = os.path.join(_LOG_DIR, "scan_debug.log")

_configured = False


def setup_logging():
    global _configured
    if _configured:
        return
    _configured = True

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    err_handler = RotatingFileHandler(
        _ERROR_LOG, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    err_handler.setLevel(logging.WARNING)
    err_handler.setFormatter(fmt)

    app_handler = RotatingFileHandler(
        _APP_LOG, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(fmt)

    scan_handler = RotatingFileHandler(
        _SCAN_LOG, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    scan_handler.setLevel(logging.INFO)
    scan_handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(err_handler)
    root.addHandler(app_handler)
    root.addHandler(console)

    scan_logger = logging.getLogger("scanner.scan")
    scan_logger.setLevel(logging.INFO)
    scan_logger.addHandler(scan_handler)

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name):
    setup_logging()
    return logging.getLogger(name)
