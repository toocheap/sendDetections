#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Logging configuration for the sendDetections package.
Provides structured logging setup with JSON formatting for machine readability
and console formatting for human readability.
Uses Python 3.10+ type annotations.
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
# Use standard library typing (Python 3.10+)
from typing import Any, Optional, cast
# Collections
from collections.abc import Mapping, Sequence

# Determine if we're in a production environment
IS_PRODUCTION = os.environ.get("ENVIRONMENT", "").lower() == "production"

# Default logging level
DEFAULT_LOG_LEVEL = logging.INFO

# Console colors for better readability in interactive mode
class Colors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[37m"


class JSONFormatter(logging.Formatter):
    """
    Custom log formatter that outputs JSON to make logs machine-readable.
    """
    def __init__(self, include_timestamp: bool = True) -> None:
        """
        Initialize the JSON formatter.
        
        Args:
            include_timestamp: Whether to include a timestamp in the logs
        """
        super().__init__()
        self.include_timestamp = include_timestamp
        
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON string.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON-formatted log string
        """
        log_data: dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add timestamp if configured
        if self.include_timestamp:
            log_data["timestamp"] = datetime.fromtimestamp(record.created).isoformat()
            
        # Include exception info if available
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
            
        # Add any extra attributes from the LogRecord
        for key, value in record.__dict__.items():
            if key not in [
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "id", "levelname", "levelno", "lineno", "module",
                "msecs", "message", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "thread", "threadName"
            ]:
                log_data[key] = value
                
        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """
    Custom log formatter for console output with colors.
    """
    DEFAULT_FORMAT = "[%(asctime)s] %(levelname)s [%(name)s:%(funcName)s:%(lineno)d] %(message)s"
    
    LEVEL_COLORS = {
        "DEBUG": Colors.GRAY,
        "INFO": Colors.GREEN,
        "WARNING": Colors.YELLOW,
        "ERROR": Colors.RED,
        "CRITICAL": Colors.MAGENTA
    }
    
    def __init__(self, use_colors: bool = True) -> None:
        """
        Initialize the console formatter.
        
        Args:
            use_colors: Whether to use colors in the output
        """
        super().__init__(fmt=self.DEFAULT_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        self.use_colors = use_colors and sys.stdout.isatty()
        
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record for console output, optionally with colors.
        
        Args:
            record: The log record to format
            
        Returns:
            Formatted log string
        """
        # Clone the record to avoid modifying the original
        record_copy = logging.makeLogRecord(record.__dict__)
        
        # Add color codes if enabled
        if self.use_colors:
            color = self.LEVEL_COLORS.get(record_copy.levelname, "")
            if color:
                record_copy.levelname = f"{color}{record_copy.levelname}{Colors.RESET}"
                
        # Format the record
        result = super().format(record_copy)
        
        # Format exception differently for console
        if record.exc_info:
            exception_text = self.formatException(record.exc_info)
            # Indent the traceback for readability
            indented_traceback = "\n    ".join(exception_text.split("\n"))
            result += f"\n    {indented_traceback}"
            
        return result


def configure_logging(
    level: int | str = DEFAULT_LOG_LEVEL,
    json_output: bool = False,
    log_file: Optional[str] = None
) -> None:
    """
    Configure the logging system for the application.
    
    Args:
        level: Logging level (name or number)
        json_output: Whether to output logs in JSON format
        log_file: Optional file to write logs to
    """
    # Convert string level to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper(), DEFAULT_LOG_LEVEL)
        
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Choose the appropriate formatter
    if json_output:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ConsoleFormatter(use_colors=not IS_PRODUCTION))
        
    # Add console handler
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        try:
            # Make sure the directory exists
            log_path = Path(log_file).absolute()
            log_dir = log_path.parent
            if not log_dir.exists():
                log_dir.mkdir(parents=True, exist_ok=True)
                
            # Create the file handler
            file_handler = logging.FileHandler(str(log_path))
            file_handler.setLevel(level)
            # Always use JSON for file logging for better analysis
            file_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(file_handler)
            
            print(f"Logging to file: {log_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error setting up log file {log_file}: {str(e)}", file=sys.stderr)
            traceback.print_exc()
        
    # Set specific levels for third-party libraries to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    
    # Log configuration
    root_logger.debug(
        "Logging configured: level=%s, json=%s, file=%s",
        logging.getLevelName(level),
        json_output,
        log_file or "none"
    )