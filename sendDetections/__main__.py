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
    
    # Files to process (primary parameter)
    parser.add_argument(
        "files", 
        nargs="*", 
        help="Files to process (CSV or JSON, defaults to all CSVs in sample/ if none specified)"
    )
    
    # API and authentication options
    parser.add_argument(
        "--token", "-t",
        help="API token (overrides RF_API_TOKEN env var)"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode (data will not be saved to RF Intelligence Cloud)"
    )
    parser.add_argument(
        "--org-id",
        help="Organization ID to associate with the detections (for multi-org setups)"
    )
    
    # Organization ID is specified directly without listing functionality
    
    # Input options
    parser.add_argument(
        "--input-dir", 
        type=Path, 
        help="Directory containing input files (default: sample/)"
    )
    parser.add_argument(
        "--pattern", 
        help="Filename pattern to match (default: sample_*.csv for CSV files)"
    )
    
    # Processing options
    parser.add_argument(
        "--concurrent", "-c",
        type=int,
        default=5,
        help="Maximum number of concurrent requests (default: 5)"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=100,
        help="Maximum number of detections per batch (default: 100)"
    )
    parser.add_argument(
        "--max-retries", "-r",
        type=int,
        default=3,
        help="Maximum number of retry attempts for API calls (default: 3)"
    )
    parser.add_argument(
        "--no-retry",
        action="store_true",
        help="Disable automatic retries on API errors"
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bars"
    )
    
    # Export options
    parser.add_argument(
        "--export-metrics",
        action="store_true",
        help="Export performance metrics to a JSON file"
    )
    parser.add_argument(
        "--metrics-file",
        type=str,
        help="Path to save performance metrics (default: auto-generated)"
    )
    parser.add_argument(
        "--export-results",
        action="store_true",
        help="Export processing results to files"
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        help="Directory for exported results (default: current directory)"
    )
    parser.add_argument(
        "--export-format",
        choices=["json", "csv", "html", "all"],
        default="all",
        help="Export format for results (default: all)"
    )
    parser.add_argument(
        "--analyze-errors",
        action="store_true",
        help="Analyze errors and provide suggestions"
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
    
    # Logging options
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
    
    return parser

async def handle_submit_command(args) -> int:
    """
    Handle the submit command: automatically detect file type and process files accordingly.
    Handles both CSV and JSON files, converting CSV files automatically.
    
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
        max_concurrent = args.concurrent or get_config("max_concurrent", 5)
        batch_size = args.batch_size or get_config("batch_size", 100)
        max_retries = args.max_retries or get_config("max_retries", 3)
        
        # Check for organization ID
        org_id = args.org_id or get_config("organization_id")
        
        # Initialize batch processor
        processor = BatchProcessor(
            api_token=api_token,
            max_concurrent=max_concurrent,
            batch_size=batch_size,
            max_retries=max_retries,
            show_progress=not args.no_progress,
            organization_id=org_id
        )
        
        # Expand glob patterns in file arguments if provided
        if args.files:
            file_paths = []
            for pattern in args.files:
                # If the pattern contains a wildcard, expand it
                if '*' in pattern or '?' in pattern:
                    matches = list(Path('.').glob(pattern))
                    file_paths.extend(matches)
                else:
                    # Otherwise just add the single path
                    file_paths.append(Path(pattern))
        else:
            # No files specified, try to use default directory
            input_dir = args.input_dir or get_config("sample_dir", SAMPLE_DIR)
            csv_pattern = args.pattern or get_config("csv_pattern", "sample_*.csv")
            
            logger.info(f"No files specified, looking for CSV files in {input_dir} with pattern {csv_pattern}")
            file_paths = list(Path(input_dir).glob(csv_pattern))
            
        if not file_paths:
            logger.error("No files found. Please specify files to process.")
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
        logger.error("Unexpected error during submission: %s", str(e), exc_info=True)
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
    logger.info("sendDetections starting")
    
    try:
        # Default behavior is to process files
        return asyncio.run(handle_submit_command(args))
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130  # Standard Unix exit code for SIGINT
    except Exception as e:
        logger.critical("Unhandled exception: %s", str(e), exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())