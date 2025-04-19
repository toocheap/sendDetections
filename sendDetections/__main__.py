"""
Main entry point for the sendDetections package when run as a module.

Uses Python 3.10+ type annotations.
"""

import os
import sys
import json
import traceback
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

from sendDetections.csv_converter import CSVConverter
from sendDetections.enhanced_api_client import EnhancedApiClient
from sendDetections.config import SAMPLE_DIR
from sendDetections.logging_config import configure_logging
from sendDetections.errors import (
    SendDetectionsError, ApiError, ApiAuthenticationError,
    ApiRateLimitError, ApiServerError, ApiConnectionError,
    ApiTimeoutError, PayloadValidationError, CSVConversionError
)

# Set up logger
logger = logging.getLogger("sendDetections")


def setup_argparse():
    """
    Set up command-line argument parsing.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="CSV to JSON Converter and Recorded Future Detection API Client"
    )
    
    # Common parameters
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Set logging level (default: info)"
    )
    parser.add_argument(
        "--json-logs",
        action="store_true",
        help="Output logs in JSON format"
    )
    parser.add_argument(
        "--log-file",
        help="Write logs to specified file"
    )
    
    # Create subcommands
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
    send_parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retry attempts for API calls (default: 3)"
    )
    send_parser.add_argument(
        "--no-retry",
        action="store_true",
        help="Disable automatic retries on API errors"
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
    convert_send_parser.add_argument(
        "--pattern", 
        help="CSV filename pattern to match (default: sample_*.csv)"
    )
    convert_send_parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retry attempts for API calls (default: 3)"
    )
    convert_send_parser.add_argument(
        "--no-retry",
        action="store_true",
        help="Disable automatic retries on API errors"
    )
    
    return parser


def handle_convert_command(args) -> int:
    """
    Handle the convert command: convert CSV files to JSON.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Setup converter with specified options
        input_dir = args.input_dir or SAMPLE_DIR
        
        logger.info("Converting CSV files from %s", input_dir)
        
        converter = CSVConverter(
            input_dir=input_dir,
            output_dir=args.output_dir,
            csv_pattern=args.pattern or "sample_*.csv"
        )
        
        # Process specified files or run batch conversion
        if args.files:
            json_files = []
            for csv_file in args.files:
                csv_path = Path(csv_file)
                try:
                    json_path = converter.convert_file(csv_path)
                    json_files.append(json_path)
                    logger.info("Converted %s -> %s", csv_path, json_path)
                except CSVConversionError as e:
                    logger.error("Conversion error: %s", str(e))
        else:
            # Batch convert all matching files
            logger.info("Running batch conversion with pattern: %s", converter.csv_pattern)
            json_files = converter.run()
            
        if not json_files:
            logger.warning("No files were successfully converted.")
            return 1
            
        logger.info("Successfully converted %d file(s)", len(json_files))
        return 0
    
    except CSVConversionError as e:
        logger.error("CSV conversion error: %s", e.message)
        return 1
    except Exception as e:
        logger.error("Unexpected error during conversion: %s", str(e), exc_info=True)
        return 1


def handle_send_command(args) -> int:
    """
    Handle the send command: send JSON files to the API.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get API token
        api_token = args.token or os.getenv("RF_API_TOKEN")
        if not api_token:
            logger.error("API token is required. Use --token or set RF_API_TOKEN in .env.")
            return 1
        
        # Initialize API client
        client = EnhancedApiClient(
            api_token=api_token,
            max_retries=args.max_retries if not args.no_retry else 0
        )
        
        success_count = 0
        failed_count = 0
        
        for file_path in args.files:
            path = Path(file_path)
            logger.info("Processing: %s", path)
            
            try:
                # Read JSON payload
                with path.open(encoding="utf-8") as f:
                    try:
                        payload = json.load(f)
                    except json.JSONDecodeError as e:
                        logger.error("Invalid JSON in %s: %s", path.name, str(e))
                        failed_count += 1
                        continue
                
                # Send to API
                response = client.send_data(
                    payload, 
                    debug=args.debug,
                    retry=not args.no_retry
                )
                
                # Display response summary
                if "summary" in response:
                    summary = response["summary"]
                    logger.info(
                        "Success: %d submitted, %d processed, %d dropped", 
                        summary.get("submitted", 0),
                        summary.get("processed", 0),
                        summary.get("dropped", 0)
                    )
                else:
                    logger.info("Success: Payload sent to API")
                
                success_count += 1
                    
            except PayloadValidationError as e:
                logger.error("Validation error in %s: %s", path.name, e.message)
                failed_count += 1
            except ApiAuthenticationError as e:
                logger.error("Authentication error: %s", e.message)
                return 1  # Stop processing on authentication errors
            except ApiRateLimitError as e:
                logger.error("Rate limit exceeded: %s (retry after: %s seconds)", 
                            e.message, e.retry_after or "unknown")
                failed_count += 1
            except ApiServerError as e:
                logger.error("Server error (status code %s): %s", e.status_code, e.message)
                failed_count += 1
            except ApiConnectionError as e:
                logger.error("Connection error: %s", e.message)
                failed_count += 1
            except ApiTimeoutError as e:
                logger.error("Request timed out: %s", e.message)
                failed_count += 1
            except ApiError as e:
                logger.error("API error: %s", e.message)
                failed_count += 1
            except Exception as e:
                logger.error("Unexpected error processing %s: %s", path.name, str(e), exc_info=True)
                failed_count += 1
        
        # Report final status
        total = len(args.files)
        logger.info("Completed: %d of %d file(s) successfully sent (%d failed)", 
                   success_count, total, failed_count)
        
        # Return success if at least one file was processed successfully
        return 0 if success_count > 0 else 1
    
    except Exception as e:
        logger.error("Unexpected error during API submission: %s", str(e), exc_info=True)
        return 1


def handle_convert_send_command(args) -> int:
    """
    Handle the convert-send command: convert CSV files and send them to the API.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get API token
        api_token = args.token or os.getenv("RF_API_TOKEN")
        if not api_token:
            logger.error("API token is required. Use --token or set RF_API_TOKEN in .env.")
            return 1
        
        # Setup converter
        input_dir = args.input_dir or SAMPLE_DIR
        
        logger.info("Converting and sending CSV files from %s", input_dir)
        
        converter = CSVConverter(
            input_dir=input_dir,
            csv_pattern=args.pattern or "sample_*.csv"
        )
        
        # Initialize API client
        client = EnhancedApiClient(
            api_token=api_token,
            max_retries=args.max_retries if not args.no_retry else 0
        )
        
        # Convert files
        if args.files:
            json_files = []
            for csv_file in args.files:
                csv_path = Path(csv_file)
                try:
                    json_path = converter.convert_file(csv_path)
                    json_files.append(json_path)
                    logger.info("Converted %s -> %s", csv_path, json_path)
                except CSVConversionError as e:
                    logger.error("Conversion error: %s", str(e))
        else:
            # Batch convert all matching files
            logger.info("Running batch conversion with pattern: %s", converter.csv_pattern)
            json_files = converter.run()
            
        if not json_files:
            logger.warning("No files were successfully converted. Nothing to send.")
            return 1
        
        # Send converted files
        success_count = 0
        failed_count = 0
        
        for json_path in json_files:
            logger.info("Sending: %s", json_path)
            
            try:
                # Read JSON payload
                with json_path.open(encoding="utf-8") as f:
                    try:
                        payload = json.load(f)
                    except json.JSONDecodeError as e:
                        logger.error("Invalid JSON in %s: %s", json_path.name, str(e))
                        failed_count += 1
                        continue
                
                # Send to API
                response = client.send_data(
                    payload, 
                    debug=args.debug,
                    retry=not args.no_retry
                )
                
                # Display response summary
                if "summary" in response:
                    summary = response["summary"]
                    logger.info(
                        "Success: %d submitted, %d processed, %d dropped", 
                        summary.get("submitted", 0),
                        summary.get("processed", 0),
                        summary.get("dropped", 0)
                    )
                else:
                    logger.info("Success: Payload sent to API")
                
                success_count += 1
                    
            except PayloadValidationError as e:
                logger.error("Validation error in %s: %s", json_path.name, e.message)
                failed_count += 1
            except ApiAuthenticationError as e:
                logger.error("Authentication error: %s", e.message)
                return 1  # Stop processing on authentication errors
            except ApiRateLimitError as e:
                logger.error("Rate limit exceeded: %s (retry after: %s seconds)", 
                            e.message, e.retry_after or "unknown")
                failed_count += 1
            except ApiServerError as e:
                logger.error("Server error (status code %s): %s", e.status_code, e.message)
                failed_count += 1
            except ApiConnectionError as e:
                logger.error("Connection error: %s", e.message)
                failed_count += 1
            except ApiTimeoutError as e:
                logger.error("Request timed out: %s", e.message)
                failed_count += 1
            except ApiError as e:
                logger.error("API error: %s", e.message)
                failed_count += 1
            except Exception as e:
                logger.error("Unexpected error processing %s: %s", json_path.name, str(e), exc_info=True)
                failed_count += 1
        
        # Report final status
        logger.info("Completed: %d of %d file(s) successfully sent (%d failed)", 
                   success_count, len(json_files), failed_count)
        
        # Return success if at least one file was processed successfully
        return 0 if success_count > 0 else 1
    
    except Exception as e:
        logger.error("Unexpected error during convert-send operation: %s", str(e), exc_info=True)
        return 1


def main() -> int:
    """
    Main entry point for the sendDetections module.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Configure logging
    configure_logging(
        level=args.log_level.upper(),
        json_output=args.json_logs,
        log_file=args.log_file
    )
    
    # Log startup information
    logger.info("sendDetections starting: command=%s", args.command or "none")
    
    try:
        # Ensure a command is specified
        if not args.command:
            logger.error("No command specified. Use 'convert', 'send', or 'convert-send'.")
            parser.print_help()
            return 1
        
        # Dispatch to appropriate handler based on command
        if args.command == "convert":
            return handle_convert_command(args)
        elif args.command == "send":
            return handle_send_command(args)
        elif args.command == "convert-send":
            return handle_convert_send_command(args)
        else:
            logger.error("Unknown command: %s", args.command)
            return 1
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130  # Standard Unix exit code for SIGINT
    except Exception as e:
        logger.critical("Unhandled exception: %s", str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())