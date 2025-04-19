#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Debug script to test the logging configuration.
"""

import sys
from pathlib import Path
from sendDetections.logging_config import configure_logging

# Configure logging with file output
log_file = Path("debug_log.json").absolute()
print(f"Attempting to log to: {log_file}", file=sys.stderr)

try:
    configure_logging(level="DEBUG", json_output=True, log_file=str(log_file))
    
    # Import the logger after configuration
    import logging
    logger = logging.getLogger("test_logger")
    
    # Log some messages
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    print(f"Logging should be complete. Check {log_file} for the results.", file=sys.stderr)
    
except Exception as e:
    print(f"Error during logging test: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()