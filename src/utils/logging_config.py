"""
Logging Configuration for Accessibility Automation Agent
Uses loguru for structured logging with file rotation and multiple handlers.

Features:
    - Console logging with color output
    - File logging with rotation (10MB, 5 backups)
    - Separate log files for UFO2, GUIrilla, and errors
    - Configurable log levels
"""

import sys
import os
from pathlib import Path
from loguru import logger


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    """
    Configure application-wide logging with loguru.

    Sets up multiple log handlers:
        - Console (stderr) with colored output
        - Main application log (app.log)
        - UFO2-specific log (ufo2.log)
        - GUIrilla-specific log (guirilla.log)
        - Error-only log (errors.log)

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
    """
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Remove default handler to avoid duplicate logs
    logger.remove()

    # --- Console Handler ---
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level=level,
        colorize=True,
    )

    # --- Main Application Log ---
    logger.add(
        log_path / "app.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=level,
        rotation="10 MB",
        retention="5",
        compression="zip",
        encoding="utf-8",
    )

    # --- UFO2 Detection Log ---
    logger.add(
        log_path / "ufo2.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG",
        filter=lambda record: "ufo2" in record["name"].lower(),
        rotation="10 MB",
        retention="5",
        encoding="utf-8",
    )

    # --- GUIrilla Detection Log ---
    logger.add(
        log_path / "guirilla.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG",
        filter=lambda record: "guirilla" in record["name"].lower(),
        rotation="10 MB",
        retention="5",
        encoding="utf-8",
    )

    # --- Error-Only Log ---
    logger.add(
        log_path / "errors.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}\n{exception}"
        ),
        level="ERROR",
        rotation="10 MB",
        retention="10",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    logger.info("Logging system initialized successfully")
    logger.info(f"Log level: {level} | Log directory: {log_path.resolve()}")


def get_logger(name: str = "accessibility_agent"):
    """
    Get a named logger instance.

    Args:
        name: Logger name for filtering (e.g., 'ufo2', 'guirilla', 'voice')

    Returns:
        Logger instance bound with the given name
    """
    return logger.bind(name=name)


__all__ = ["logger", "setup_logging", "get_logger"]
