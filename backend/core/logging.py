import sys
from loguru import logger
from core.config import settings

def setup_logging():
    logger.remove()
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
        level="DEBUG" if settings.environment == "development" else "INFO",
        serialize=settings.environment == "production",
    )
    return logger
