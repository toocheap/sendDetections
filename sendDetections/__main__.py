"""
Main entry point for the sendDetections package when run as a module.

Uses Python 3.10+ type annotations.
"""

import os
import sys
import json
import asyncio
import traceback
import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sendDetections.csv_converter import CSVConverter
from sendDetections.enhanced_api_client import EnhancedApiClient
from sendDetections.async_api_client import AsyncApiClient
from sendDetections.batch_processor import BatchProcessor
from sendDetections.config import SAMPLE_DIR
from sendDetections.logging_config import configure_logging
from sendDetections.exporters import ResultExporter
from sendDetections.error_analyzer import ErrorAnalyzer, ErrorCollection
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
    
    # Configuration file parameters
    parser.add_argument(
        "--config",
        help="Path to configuration file (YAML or JSON)"
    )
    parser.add_argument(
        "--profile",
        default="default",
        help="Configuration profile to use (for multi-environment setups)"
    )
    
    # Create subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Convert command
    convert_parser = subparsers.add_parser(
        "convert", 
        help="Convert CSV files to JSON payload format"
    )
    
    
    # Batch command
    batch_parser = subparsers.add_parser(
        "batch",
        help="Process multiple files with efficient concurrent batch processing"
    )
    batch_parser.add_argument(
        "files",
        nargs="+",
        help="JSON or CSV files to process (use *.json or *.csv for multiple files)"
    )
    batch_parser.add_argument(
        "--token", "-t",
        help="API token (overrides RF_API_TOKEN env var)"
    )
    batch_parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode (data will not be saved to RF Intelligence Cloud)"
    )
    batch_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum number of concurrent requests (default: 5)"
    )
    batch_parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Maximum number of detections per batch (default: 100)"
    )
    batch_parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retry attempts for API calls (default: 3)"
    )
    batch_parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bars"
    )
    batch_parser.add_argument(
        "--export-metrics",
        action="store_true",
        help="Export performance metrics to a JSON file"
    )
    batch_parser.add_argument(
        "--metrics-file",
        type=str,
        help="Path to save performance metrics (default: auto-generated)"
    )
    batch_parser.add_argument(
        "--export-results",
        action="store_true",
        help="Export processing results to files"
    )
    batch_parser.add_argument(
        "--export-dir",
        type=str,
        help="Directory for exported results (default: current directory)"
    )
    batch_parser.add_argument(
        "--export-format",
        choices=["json", "csv", "html", "all"],
        default="all",
        help="Export format for results (default: all)"
    )
    batch_parser.add_argument(
        "--analyze-errors",
        action="store_true",
        help="Analyze errors and provide suggestions"
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
        from sendDetections.config import get_config
        
        # Setup converter with specified options
        input_dir = args.input_dir or get_config("sample_dir", SAMPLE_DIR)
        csv_pattern = args.pattern or get_config("csv_pattern", "sample_*.csv")
        csv_encoding = get_config("csv_encoding", "utf-8")
        
        logger.info("Converting CSV files from %s", input_dir)
        
        converter = CSVConverter(
            input_dir=input_dir,
            output_dir=args.output_dir,
            csv_pattern=csv_pattern,
            encoding=csv_encoding
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
        from sendDetections.config import get_config, get_api_url
        
        # Get API token
        api_token = args.token or get_config("api_token") or os.getenv("RF_API_TOKEN")
        if not api_token:
            logger.error("API token is required. Use --token, set RF_API_TOKEN in .env, or configure in config file.")
            return 1
        
        # Get configuration values with command-line priority
        max_retries = args.max_retries or get_config("max_retries", 3)
        
        # Initialize API client
        client = EnhancedApiClient(
            api_token=api_token,
            api_url=get_api_url(),
            max_retries=max_retries if not args.no_retry else 0
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


async def handle_batch_command(args) -> int:
    """
    Handle the batch command: process multiple files concurrently using async API.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        from sendDetections.config import get_config
        
        # Get API token
        api_token = args.token or get_config("api_token") or os.getenv("RF_API_TOKEN")
        if not api_token:
            logger.error("API token is required. Use --token, set RF_API_TOKEN in .env, or configure in config file.")
            return 1
        
        # Get configuration values with command-line priority
        max_concurrent = args.max_concurrent or get_config("max_concurrent", 5)
        batch_size = args.batch_size or get_config("batch_size", 100)
        max_retries = args.max_retries or get_config("max_retries", 3)
        
        # Initialize batch processor
        processor = BatchProcessor(
            api_token=api_token,
            max_concurrent=max_concurrent,
            batch_size=batch_size,
            max_retries=max_retries,
            show_progress=not args.no_progress
        )
        
        # Expand glob patterns in file arguments
        file_paths = []
        for pattern in args.files:
            # If the pattern contains a wildcard, expand it
            if '*' in pattern or '?' in pattern:
                matches = list(Path('.').glob(pattern))
                file_paths.extend(matches)
            else:
                # Otherwise just add the single path
                file_paths.append(Path(pattern))
        
        if not file_paths:
            logger.error("No files matched the specified patterns.")
            return 1
            
        logger.info("Found %d files to process", len(file_paths))
        
        # Separate JSON and CSV files
        json_files = [f for f in file_paths if f.suffix.lower() == '.json']
        csv_files = [f for f in file_paths if f.suffix.lower() == '.csv']
        
        json_count = len(json_files)
        csv_count = len(csv_files)
        other_count = len(file_paths) - json_count - csv_count
        
        if other_count > 0:
            logger.warning("Ignoring %d files with unsupported extensions", other_count)
        
        # Process files according to their type
        total_submitted = 0
        total_processed = 0
        total_dropped = 0
        
        # Collection of all results for potential export
        all_results = []
        
        # Error collection for analysis
        error_collection = ErrorCollection()
        
        # Setup export options
        metrics_file = None
        if args.metrics_file:
            metrics_file = Path(args.metrics_file)
            
        # Setup results exporter if needed
        results_exporter = None
        if args.export_results:
            export_dir = args.export_dir
            results_exporter = ResultExporter(export_dir=export_dir)
        
        # Process JSON files
        if json_files:
            logger.info("Processing %d JSON files", len(json_files))
            json_result = await processor.process_files(
                json_files, 
                debug=args.debug,
                export_metrics=args.export_metrics,
                metrics_file=metrics_file and metrics_file.with_suffix('.json_metrics.json')
            )
            
            if "summary" in json_result:
                summary = json_result["summary"]
                total_submitted += summary.get("submitted", 0)
                total_processed += summary.get("processed", 0)
                total_dropped += summary.get("dropped", 0)
                
                logger.info("JSON files: %d submitted, %d processed, %d dropped",
                           summary.get("submitted", 0),
                           summary.get("processed", 0),
                           summary.get("dropped", 0))
                           
                # Add to results collection
                all_results.append(json_result)
                
                # Record any errors for analysis
                if args.analyze_errors and "errors" in json_result:
                    for error in json_result.get("errors", []):
                        error_collection.add_error(error, {"source": "json_processing"})
        
        # Process CSV files
        if csv_files:
            logger.info("Processing %d CSV files", len(csv_files))
            csv_result = await processor.process_csv_files(
                csv_files, 
                debug=args.debug,
                export_metrics=args.export_metrics,
                metrics_file=metrics_file and metrics_file.with_suffix('.csv_metrics.json')
            )
            
            if "summary" in csv_result:
                summary = csv_result["summary"]
                total_submitted += summary.get("submitted", 0)
                total_processed += summary.get("processed", 0)
                total_dropped += summary.get("dropped", 0)
                
                logger.info("CSV files: %d submitted, %d processed, %d dropped",
                           summary.get("submitted", 0),
                           summary.get("processed", 0),
                           summary.get("dropped", 0))
                           
                # Add to results collection
                all_results.append(csv_result)
                
                # Record any errors for analysis
                if args.analyze_errors and "errors" in csv_result:
                    for error in csv_result.get("errors", []):
                        error_collection.add_error(error, {"source": "csv_processing"})
        
        # Total summary
        logger.info("Total: %d submitted, %d processed, %d dropped",
                   total_submitted, total_processed, total_dropped)
        
        # Export results if requested
        if args.export_results and results_exporter and all_results:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_filename = f"senddetections_{timestamp}"
                
                # Get errors for export
                errors_list = error_collection.get_errors()
                
                # Export based on format
                export_format = args.export_format.lower()
                
                if export_format == "json" or export_format == "all":
                    json_path = results_exporter.export_json(
                        {"results": all_results, "summary": {
                            "total_submitted": total_submitted,
                            "total_processed": total_processed,
                            "total_dropped": total_dropped
                        }},
                        filename=f"{base_filename}.json"
                    )
                    logger.info("Results exported to JSON: %s", json_path)
                
                if export_format == "csv" or export_format == "all":
                    csv_path = results_exporter.export_summary_csv(
                        all_results,
                        filename=f"{base_filename}_summary.csv"
                    )
                    logger.info("Summary exported to CSV: %s", csv_path)
                    
                    if errors_list:
                        errors_path = results_exporter.export_errors_csv(
                            errors_list,
                            filename=f"{base_filename}_errors.csv"
                        )
                        logger.info("Errors exported to CSV: %s", errors_path)
                
                if export_format == "html" or export_format == "all":
                    report_path = results_exporter.generate_report(
                        all_results,
                        errors_list,
                        filename=f"{base_filename}_report.html"
                    )
                    logger.info("HTML report generated: %s", report_path)
                    
            except Exception as e:
                logger.error("Error exporting results: %s", str(e))
        
        # Analyze errors if requested
        if args.analyze_errors and error_collection.error_count > 0:
            try:
                analysis_result = error_collection.analyze()
                
                # Print error analysis report
                print("\nError Analysis Report:")
                print("======================")
                print(analysis_result["report"])
                
                # Export error analysis if exporting results
                if args.export_results and results_exporter:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    analysis_path = results_exporter.export_json(
                        analysis_result,
                        filename=f"error_analysis_{timestamp}.json"
                    )
                    logger.info("Error analysis exported to: %s", analysis_path)
                    
            except Exception as e:
                logger.error("Error analyzing errors: %s", str(e))
                   
        return 0 if total_processed > 0 else 1
        
    except ApiAuthenticationError as e:
        logger.error("Authentication error: %s", e.message)
        return 1
    except ApiError as e:
        logger.error("API error: %s", e.message)
        return 1
    except Exception as e:
        logger.error("Unexpected error during batch processing: %s", str(e), exc_info=True)
        return 1


def handle_visualize_command(args) -> int:
    """
    Handle the visualize command: launch interactive dashboard for results visualization.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Try to import visualization dependencies - these are optional
        try:
            from sendDetections.visualize import start_dashboard, VIZ_AVAILABLE
            if not VIZ_AVAILABLE:
                logger.error(
                    "Visualization dependencies not installed. "
                    "Install with: pip install -e \".[viz]\""
                )
                return 1
        except ImportError:
            logger.error(
                "Visualization module not available. "
                "Install required dependencies with: pip install -e \".[viz]\""
            )
            return 1
            
        # Verify file exists
        file_path = Path(args.file)
        if not file_path.exists():
            logger.error("Results file not found: %s", file_path)
            return 1
            
        if not file_path.suffix.lower() == '.json':
            logger.warning(
                "Expected a JSON file but got %s. "
                "The dashboard may not work correctly.",
                file_path.suffix
            )
            
        # Launch the dashboard
        logger.info("Launching visualization dashboard for %s", file_path)
        try:
            # Start the dashboard (this will block until the server is stopped)
            start_dashboard(
                file_path=file_path,
                port=args.port,
                open_browser=not args.no_browser,
                debug=args.debug
            )
            return 0
        except KeyboardInterrupt:
            logger.info("Dashboard server stopped by user")
            return 0
            
    except Exception as e:
        logger.error("Failed to start visualization dashboard: %s", str(e), exc_info=True)
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
        from sendDetections.config import get_config, get_api_url
        
        # Get API token
        api_token = args.token or get_config("api_token") or os.getenv("RF_API_TOKEN")
        if not api_token:
            logger.error("API token is required. Use --token, set RF_API_TOKEN in .env, or configure in config file.")
            return 1
        
        # Get configuration values with command-line priority
        max_retries = args.max_retries or get_config("max_retries", 3)
        
        # Setup converter
        input_dir = args.input_dir or get_config("sample_dir", SAMPLE_DIR)
        csv_pattern = args.pattern or get_config("csv_pattern", "sample_*.csv")
        
        logger.info("Converting and sending CSV files from %s", input_dir)
        
        converter = CSVConverter(
            input_dir=input_dir,
            csv_pattern=csv_pattern
        )
        
        # Initialize API client
        client = EnhancedApiClient(
            api_token=api_token,
            api_url=get_api_url(),
            max_retries=max_retries if not args.no_retry else 0
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
    
    # Initialize configuration manager with provided file and profile
    from sendDetections.config import ConfigManager, config_manager
    
    if args.config or args.profile != "default":
        # Create a new config manager with the specified options
        new_config_manager = ConfigManager(
            config_file=args.config,
            profile=args.profile
        )
        
        # Replace the default config manager
        # This is a bit hacky but allows us to keep the module-level imports working
        import sendDetections.config
        sendDetections.config.config_manager = new_config_manager
        
        if args.config:
            logger.info("Using configuration file: %s (profile: %s)", args.config, args.profile)
        else:
            logger.info("Using configuration profile: %s", args.profile)
    
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
        elif args.command == "batch":
            return asyncio.run(handle_batch_command(args))
        elif args.command == "visualize":
            return handle_visualize_command(args)
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