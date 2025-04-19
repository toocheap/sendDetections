#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified script for CSV to Payload JSON conversion and Recorded Future Detection API submission.

Usage examples:
  python3 sendDetections.py convert          # Batch convert all sample/*.csv files to .json
  python3 sendDetections.py send sample/sample_common.json --token <TOKEN>
  python3 sendDetections.py convert-send     # Convert and send all CSVs in the sample directory
"""

import argparse
import json as jsonlib
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv

from sendDetections.csv_converter import CSVConverter, CSVConversionError
from sendDetections.api_client import DetectionApiClient, ApiError
from sendDetections.config import SAMPLE_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("sendDetections")

# --- For CLI subprocess integration test: requests.post mock ---
if os.environ.get("MOCK_REQUESTS") == "1":
    import requests
    class MockResponse:
        def __init__(self):
            self.status_code = 200
            self._json = {
                "summary": {"submitted": 1, "processed": 1, "dropped": 0, "transient_ids": []},
                "options": {"debug": True}
            }
            self.text = ""
            self.content = b""
        def raise_for_status(self):
            pass
        def json(self):
            return self._json
    def mock_post(url, json, headers, **kwargs):
        # Only assert True if options.debug is specified
        if "options" in json and "debug" in json["options"]:
            assert json["options"]["debug"] is True
        return MockResponse()
    requests.post = mock_post


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="CSV to JSON conversion and Recorded Future Detection API submission tool"
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Convert command
    convert_parser = subparsers.add_parser(
        "convert", 
        help="Convert CSV files to JSON payload format"
    )
    convert_parser.add_argument(
        "files", 
        nargs="*", 
        help="CSV files to convert (defaults to all CSVs in sample/ if none specified)"
    )
    convert_parser.add_argument(
        "--input-dir", 
        type=Path, 
        help="Directory containing input CSV files (default: sample/)"
    )
    convert_parser.add_argument(
        "--output-dir", 
        type=Path, 
        help="Directory for output JSON files (default: same as input)"
    )
    convert_parser.add_argument(
        "--pattern", 
        help="CSV filename pattern to match (default: sample_*.csv)"
    )
    
    # Send command
    send_parser = subparsers.add_parser(
        "send", 
        help="Send JSON files to the Detection API"
    )
    send_parser.add_argument(
        "files", 
        nargs="+", 
        help="JSON files to send to the API"
    )
    send_parser.add_argument(
        "--token", "-t",
        help="API token (overrides RF_API_TOKEN env var)"
    )
    send_parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode (data will not be saved to RF Intelligence Cloud)"
    )
    
    # Convert and send command
    convert_send_parser = subparsers.add_parser(
        "convert-send", 
        help="Convert CSV files and send the resulting JSON to the API"
    )
    convert_send_parser.add_argument(
        "files", 
        nargs="*", 
        help="CSV files to convert and send (defaults to all CSVs in sample/ if none specified)"
    )
    convert_send_parser.add_argument(
        "--input-dir", 
        type=Path, 
        help="Directory containing input CSV files (default: sample/)"
    )
    convert_send_parser.add_argument(
        "--token", "-t",
        help="API token (overrides RF_API_TOKEN env var)"
    )
    convert_send_parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode (data will not be saved to RF Intelligence Cloud)"
    )
    
    # Global options
    parser.add_argument(
        "--env-file", "-e",
        type=str,
        help="Path to .env file (default: .env in current directory)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    
    return parser.parse_args()


def main():
    args = parse_arguments()
    
    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Load .env file
    if args.env_file:
        load_dotenv(dotenv_path=args.env_file)
    else:
        load_dotenv()
    
    
    # Ensure a command is specified
    if not args.command:
        logger.error("No command specified. Use 'convert', 'send', or 'convert-send'.")
        return 1
    
    # Command: convert
    if args.command == "convert":
        # Setup converter with specified options
        converter = CSVConverter(
            input_dir=args.input_dir or SAMPLE_DIR,
            output_dir=args.output_dir,
            csv_pattern=args.pattern or None
        )
        
        # Process specified files or run batch conversion
        if args.files:
            json_files = []
            for csv_file in args.files:
                csv_path = Path(csv_file)
                try:
                    json_path = converter.convert_file(csv_path)
                    json_files.append(json_path)
                except CSVConversionError as e:
                    logger.error(str(e))
        else:
            # Batch convert all matching files
            json_files = converter.run()
            
        if not json_files:
            logger.warning("No files were successfully converted.")
            return 1
            
        logger.info(f"Successfully converted {len(json_files)} file(s)")
        return 0
    
    # Get API token for commands that need it
    if args.command in ["send", "convert-send"]:
        api_token = args.token or os.getenv("RF_API_TOKEN")
        if not api_token:
            logger.error("API token is required. Use --token or set RF_API_TOKEN in .env.")
            return 1
        
        # Initialize API client
        api_client = DetectionApiClient(api_token)
    
    # Command: send
    if args.command == "send":
        exit_code = 0
        for file_path in args.files:
            path = Path(file_path)
            logger.info(f"Sending: {path}")
            
            try:
                # Read JSON payload
                with path.open(encoding="utf-8") as f:
                    payload = jsonlib.load(f)
                
                # Send to API
                response = api_client.send_data(payload, debug=args.debug)
                
                # Display response summary
                if "summary" in response:
                    summary = response["summary"]
                    logger.info(f"Success: {summary.get('submitted', 0)} submitted, "
                               f"{summary.get('processed', 0)} processed, "
                               f"{summary.get('dropped', 0)} dropped")
                else:
                    logger.info("Success: Payload sent to API")
                    
            except ApiError as e:
                logger.error(f"API Error: {e.message}")
                exit_code = 1
            except Exception as e:
                logger.error(f"Error processing {path.name}: {e}")
                exit_code = 1
                
        return exit_code
    
    # Command: convert-send
    if args.command == "convert-send":
        # Setup converter
        converter = CSVConverter(
            input_dir=args.input_dir or SAMPLE_DIR
        )
        
        # Convert files
        if args.files:
            json_files = []
            for csv_file in args.files:
                csv_path = Path(csv_file)
                try:
                    json_path = converter.convert_file(csv_path)
                    json_files.append(json_path)
                except CSVConversionError as e:
                    logger.error(str(e))
        else:
            # Batch convert all matching files
            json_files = converter.run()
            
        if not json_files:
            logger.warning("No files were successfully converted. Nothing to send.")
            return 1
            
        # Send converted files
        success_count = 0
        for json_path in json_files:
            logger.info(f"Sending: {json_path}")
            
            try:
                # Read JSON payload
                with json_path.open(encoding="utf-8") as f:
                    payload = jsonlib.load(f)
                
                # Send to API
                response = api_client.send_data(payload, debug=args.debug)
                success_count += 1
                
                # Display response summary
                if "summary" in response:
                    summary = response["summary"]
                    logger.info(f"Success: {summary.get('submitted', 0)} submitted, "
                               f"{summary.get('processed', 0)} processed, "
                               f"{summary.get('dropped', 0)} dropped")
                else:
                    logger.info("Success: Payload sent to API")
                    
            except ApiError as e:
                logger.error(f"API Error: {e.message}")
            except Exception as e:
                logger.error(f"Error processing {json_path.name}: {e}")
                
        if success_count == 0:
            logger.error("No files were successfully sent.")
            return 1
            
        logger.info(f"Successfully sent {success_count} out of {len(json_files)} file(s)")
        return 0
        
    return 0


if __name__ == "__main__":
    sys.exit(main())