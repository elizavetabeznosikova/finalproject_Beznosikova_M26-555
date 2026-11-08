import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "actions.log"
LOG_FORMAT = "%(levelname)s %(asctime)s %(name)s: %(message)s"
LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S"

_configured = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _configured

    logger = logging.getLogger("valutatrade_hub")

    if _configured:
        logger.setLevel(level)
        return logger

    logger.setLevel(level)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    _configured = True
    return logger

