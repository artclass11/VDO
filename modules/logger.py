"""Logging configuration and utilities for OpenDocu-AI."""

import logging
from pathlib import Path
from typing import Optional
import structlog
from config import settings


def setup_logging(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Setup structured logging for a module.
    
    Args:
        name: Module name (__name__)
        level: Log level override
        
    Returns:
        Configured logger instance
    """
    log_level = level or settings.LOG_LEVEL
    
    # Create logs directory
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Get Python logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # File handler
    log_file = settings.LOGS_DIR / f"{name}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    
    # Add handlers if not already added
    if not logger.handlers:
        logger.addHandler(file_handler)
        if settings.DEBUG_MODE:
            logger.addHandler(console_handler)
    
    return logger
