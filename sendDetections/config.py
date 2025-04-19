"""
Configuration settings for the sendDetections package.

Configuration can be set via environment variables or loaded from a .env file.
"""

import os
from pathlib import Path
from typing import Any

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# API settings
API_URL = os.getenv("RF_API_URL", "https://api.recordedfuture.com/collective-insights/detections")

# Default HTTP headers for API requests
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# Sample data settings
SAMPLE_DIR = PROJECT_ROOT / "sample"
CSV_PATTERN = "sample_*.csv"
CSV_ENCODING = "utf-8"

# API options defaults
DEFAULT_API_OPTIONS: dict[str, Any] = {
    "debug": False,
    "summary": True
}