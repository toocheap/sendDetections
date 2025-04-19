"""
Main entry point for the sendDetections package when run as a module.
"""

import sys
import logging
from pathlib import Path

from sendDetections.csv_converter import CSVConverter
from sendDetections.api_client import DetectionApiClient, ApiError
from sendDetections.config import SAMPLE_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("sendDetections")


def main():
    """
    Entry point when run as python -m sendDetections
    Provides equivalent functionality to the sendDetections.py script
    but with simplified interface (only batch conversion).
    """
    # Import argparse here to avoid circular imports
    import argparse
    
    parser = argparse.ArgumentParser(
        description="CSV to JSON Converter for Recorded Future Detection API"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=SAMPLE_DIR,
        help="Directory containing CSV files (default: %(default)s)"
    )
    parser.add_argument(
        "--pattern",
        default="sample_*.csv",
        help="CSV filename pattern to match (default: %(default)s)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    converter = CSVConverter(
        input_dir=args.input_dir,
        csv_pattern=args.pattern
    )
    
    # Run batch conversion
    json_files = converter.run()
    
    if not json_files:
        logger.warning("No files were converted.")
        return 1
        
    logger.info(f"Successfully converted {len(json_files)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())