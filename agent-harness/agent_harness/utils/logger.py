"""
Logging utilities for Agent Harness.

Provides configurable logging setup.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str = "agent_harness",
    level: str = "INFO",
    log_format: Optional[str] = None,
    file_path: Optional[str] = None,
    max_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console: bool = True,
    colored: bool = True,
) -> logging.Logger:
    """
    Set up a logger with console and file handlers.
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log message format
        file_path: Path to log file (None for no file logging)
        max_size: Max log file size before rotation
        backup_count: Number of backup files to keep
        console: Whether to log to console
        colored: Whether to use colored console output
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Default format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    formatter = logging.Formatter(log_format)
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        if colored:
            try:
                from rich.logging import RichHandler
                console_handler = RichHandler(
                    rich_tracebacks=True,
                    show_time=True,
                    show_path=False,
                )
            except ImportError:
                pass  # Fall back to standard handler
        
        logger.addHandler(console_handler)
    
    # File handler
    if file_path:
        log_path = Path(file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_size,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def setup_logging_from_config(config: Dict[str, Any]) -> logging.Logger:
    """
    Set up logging from configuration dictionary.
    
    Args:
        config: Logging configuration
        
    Returns:
        Configured logger
    """
    log_config = config.get("logging", {})
    
    return setup_logger(
        name="agent_harness",
        level=log_config.get("level", "INFO"),
        log_format=log_config.get("format"),
        file_path=log_config.get("file", {}).get("path") if log_config.get("file", {}).get("enabled") else None,
        max_size=log_config.get("file", {}).get("max_size", 10 * 1024 * 1024),
        backup_count=log_config.get("file", {}).get("backup_count", 5),
        console=log_config.get("console", {}).get("enabled", True),
        colored=log_config.get("console", {}).get("colored", True),
    )


class LoggerMixin:
    """Mixin class to add logging capability."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return logging.getLogger(f"agent_harness.{self.__class__.__name__}")