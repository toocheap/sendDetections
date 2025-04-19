#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch processor for Recorded Future Detection API submissions.
Provides efficient, concurrent processing of large detection datasets.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence, cast
from collections.abc import Mapping

from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

from sendDetections.async_api_client import AsyncApiClient
from sendDetections.csv_converter import CSVConverter
from sendDetections.errors import (
    ApiError, PayloadValidationError, CSVConversionError
)
from sendDetections.performance import (
    PerformanceMetrics, process_with_progress, process_in_batches,
    async_measure_time
)

# Configure logger
logger = logging.getLogger(__name__)

class BatchProcessor:
    """
    Batch processor for efficiently handling large volumes of detections.
    Uses asynchronous API client for concurrent submissions.
    """
    
    def __init__(
        self, 
        api_token: str,
        api_url: Optional[str] = None,
        max_concurrent: int = 5,
        batch_size: int = 100,
        max_retries: int = 3,
        show_progress: bool = True
    ):
        """
        Initialize the batch processor.
        
        Args:
            api_token: Recorded Future API token
            api_url: Optional custom API URL
            max_concurrent: Maximum number of concurrent API requests
            batch_size: Maximum number of detections per API request
            max_retries: Maximum number of retry attempts for API errors
            show_progress: Whether to display progress bars
        """
        self.api_token = api_token
        self.api_url = api_url
        self.max_concurrent = max_concurrent
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.show_progress = show_progress
        
        # Initialize the async API client
        self.client = AsyncApiClient(
            api_token=api_token,
            api_url=api_url,
            max_retries=max_retries,
            max_concurrent=max_concurrent
        )
        
        # Performance metrics
        self.metrics = PerformanceMetrics()
        
        logger.debug(
            "BatchProcessor initialized with max_concurrent=%d, batch_size=%d",
            max_concurrent, batch_size
        )
    
    async def process_files(
        self, 
        file_paths: Sequence[Path], 
        debug: bool = False,
        export_metrics: bool = False,
        metrics_file: Optional[Path] = None
    ) -> dict[str, Any]:
        """
        Process multiple JSON files concurrently.
        
        Args:
            file_paths: Paths to JSON files containing detection payloads
            debug: Whether to enable debug mode
            export_metrics: Whether to export performance metrics
            metrics_file: Optional path to save metrics
            
        Returns:
            Aggregated results of all API calls
            
        Raises:
            ApiError: On API-related errors
            FileNotFoundError: If any file doesn't exist
            json.JSONDecodeError: If any file contains invalid JSON
        """
        if not file_paths:
            return {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
        
        # Start measuring performance
        self.metrics = PerformanceMetrics()
        self.metrics.start()
        
        # Load all payloads first to validate JSON
        payloads = []
        total_entities = 0
        
        # Load files with progress bar if enabled
        paths_iter = tqdm(file_paths, desc="Loading files", disable=not self.show_progress)
        for path in paths_iter:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                    payloads.append(payload)
                    entities_count = len(payload.get("data", []))
                    total_entities += entities_count
                    logger.debug("Loaded payload from %s with %d detections", 
                               path, entities_count)
            except FileNotFoundError:
                logger.error("File not found: %s", path)
                self.metrics.record_error("FileNotFoundError")
                raise
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON in file %s: %s", path, str(e))
                self.metrics.record_error("JSONDecodeError")
                raise
        
        # Process all payloads concurrently
        logger.info("Processing %d payload files with %d total detections", 
                  len(payloads), total_entities)
        
        # Set up async processing with progress bar
        async def process_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool, float]:
            try:
                start_time = time.time()
                result = await self.client.send_data(payload, debug=debug)
                duration = time.time() - start_time
                
                # Record successful API call
                entity_count = len(payload.get("data", []))
                self.metrics.record_api_call(duration, True, batch_size=entity_count)
                self.metrics.record_entities(entity_count)
                
                return result, True, duration
            except Exception as e:
                end_time = time.time()
                duration = end_time - start_time
                
                # Record failed API call
                self.metrics.record_api_call(duration, False)
                self.metrics.record_error(type(e).__name__)
                
                return {"error": str(e)}, False, duration
        
        # Process payloads with progress tracking
        results = []
        pbar = tqdm(
            total=len(payloads), 
            desc="Processing files", 
            unit="file",
            disable=not self.show_progress
        )
        
        for payload in payloads:
            result, success, duration = await process_payload(payload)
            results.append(result if success else result)
            
            # Update progress bar with stats
            if self.show_progress:
                pbar.update(1)
                pbar.set_postfix(
                    success=f"{self.metrics.success_calls}/{self.metrics.api_calls}",
                    entities=self.metrics.entities_processed
                )
        
        pbar.close()
        
        # Aggregate results and handle exceptions
        aggregated: dict[str, Any] = {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
        successful = 0
        failed = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception) or "error" in result:
                error_str = str(result) if isinstance(result, Exception) else result.get("error", "Unknown error")
                logger.error("Error processing file %s: %s", 
                           file_paths[i], error_str)
                failed += 1
            else:
                successful += 1
                if "summary" in result:
                    summary = result["summary"]
                    aggregated["summary"]["submitted"] += summary.get("submitted", 0)
                    aggregated["summary"]["processed"] += summary.get("processed", 0)
                    aggregated["summary"]["dropped"] += summary.get("dropped", 0)
        
        # Finalize performance metrics
        self.metrics.end()
        self.metrics.log_summary()
        
        # Export metrics if requested
        if export_metrics:
            metrics_data = self.metrics.get_summary()
            metrics_path = metrics_file or Path(f"performance_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            try:
                with open(metrics_path, "w", encoding="utf-8") as f:
                    json.dump(metrics_data, f, indent=2)
                logger.info("Performance metrics exported to %s", metrics_path)
            except Exception as e:
                logger.error("Failed to export metrics: %s", str(e))
        
        logger.info(
            "Completed batch processing: %d of %d files successful (%d failed)",
            successful, len(file_paths), failed
        )
        logger.info(
            "Summary: %d submitted, %d processed, %d dropped",
            aggregated["summary"]["submitted"],
            aggregated["summary"]["processed"],
            aggregated["summary"]["dropped"]
        )
        
        # Include performance metrics in the result
        aggregated["performance"] = self.metrics.get_summary()
        
        return aggregated
    
    async def process_csv_files(
        self, 
        csv_paths: Sequence[Path],
        debug: bool = False,
        encoding: str = "utf-8",
        export_metrics: bool = False,
        metrics_file: Optional[Path] = None
    ) -> dict[str, Any]:
        """
        Convert and process multiple CSV files concurrently.
        
        Args:
            csv_paths: Paths to CSV files to convert and send
            debug: Whether to enable debug mode
            encoding: CSV file encoding
            export_metrics: Whether to export performance metrics
            metrics_file: Optional path to save metrics
            
        Returns:
            Aggregated results of all API calls
            
        Raises:
            ApiError: On API-related errors
            CSVConversionError: If CSV conversion fails
        """
        if not csv_paths:
            return {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
        
        # Start measuring performance
        self.metrics = PerformanceMetrics()
        self.metrics.start()
        
        # Convert all CSV files to payloads with progress bar
        converter = CSVConverter()
        payloads = []
        total_entities = 0
        
        # Convert CSV files with progress bar
        paths_iter = tqdm(csv_paths, desc="Converting CSV files", disable=not self.show_progress)
        for path in paths_iter:
            try:
                conversion_start = time.time()
                payload = converter.csv_to_payload(path)
                conversion_time = time.time() - conversion_start
                
                entities_count = len(payload.get("data", []))
                total_entities += entities_count
                
                payloads.append(payload)
                logger.debug("Converted CSV file %s to payload with %d detections in %.2f seconds", 
                           path, entities_count, conversion_time)
            except CSVConversionError as e:
                logger.error("Error converting CSV file %s: %s", path, str(e))
                self.metrics.record_error("CSVConversionError")
                raise
                
        # Process all payloads concurrently
        logger.info("Processing %d converted CSV files with %d total detections", 
                  len(payloads), total_entities)
        
        # Define processing function for each payload
        async def process_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool, float]:
            try:
                start_time = time.time()
                result = await self.client.send_data(payload, debug=debug)
                duration = time.time() - start_time
                
                # Record successful API call
                entity_count = len(payload.get("data", []))
                self.metrics.record_api_call(duration, True, batch_size=entity_count)
                self.metrics.record_entities(entity_count)
                
                return result, True, duration
            except Exception as e:
                end_time = time.time()
                duration = end_time - start_time
                
                # Record failed API call
                self.metrics.record_api_call(duration, False)
                self.metrics.record_error(type(e).__name__)
                
                return {"error": str(e)}, False, duration
        
        # Process with progress tracking
        results = []
        pbar = tqdm(
            total=len(payloads), 
            desc="Processing CSV data", 
            unit="file",
            disable=not self.show_progress
        )
        
        for payload in payloads:
            result, success, duration = await process_payload(payload)
            results.append(result if success else result)
            
            # Update progress bar with stats
            if self.show_progress:
                pbar.update(1)
                pbar.set_postfix(
                    success=f"{self.metrics.success_calls}/{self.metrics.api_calls}",
                    entities=self.metrics.entities_processed,
                    rate=f"{self.metrics.entities_processed / (time.time() - self.metrics.start_time.timestamp()):.1f}/s" 
                    if self.metrics.start_time else "0/s"
                )
        
        pbar.close()
        
        # Aggregate results and handle exceptions
        aggregated: dict[str, Any] = {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
        successful = 0
        failed = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception) or "error" in result:
                error_str = str(result) if isinstance(result, Exception) else result.get("error", "Unknown error")
                logger.error("Error processing converted CSV file %s: %s", 
                           csv_paths[i], error_str)
                failed += 1
            else:
                successful += 1
                if "summary" in result:
                    summary = result["summary"]
                    aggregated["summary"]["submitted"] += summary.get("submitted", 0)
                    aggregated["summary"]["processed"] += summary.get("processed", 0)
                    aggregated["summary"]["dropped"] += summary.get("dropped", 0)
        
        # Finalize performance metrics
        self.metrics.end()
        self.metrics.log_summary()
        
        # Export metrics if requested
        if export_metrics:
            metrics_data = self.metrics.get_summary()
            metrics_path = metrics_file or Path(f"csv_performance_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            try:
                with open(metrics_path, "w", encoding="utf-8") as f:
                    json.dump(metrics_data, f, indent=2)
                logger.info("Performance metrics exported to %s", metrics_path)
            except Exception as e:
                logger.error("Failed to export metrics: %s", str(e))
        
        logger.info(
            "Completed CSV batch processing: %d of %d files successful (%d failed)",
            successful, len(csv_paths), failed
        )
        logger.info(
            "Summary: %d submitted, %d processed, %d dropped",
            aggregated["summary"]["submitted"],
            aggregated["summary"]["processed"],
            aggregated["summary"]["dropped"]
        )
        
        # Include performance metrics in the result
        aggregated["performance"] = self.metrics.get_summary()
        
        return aggregated
    
    async def process_directory(
        self, 
        directory: Path,
        pattern: str = "*.json",
        debug: bool = False,
        recursive: bool = False
    ) -> dict[str, Any]:
        """
        Process all matching files in a directory.
        
        Args:
            directory: Directory containing files to process
            pattern: Glob pattern for matching files
            debug: Whether to enable debug mode
            recursive: Whether to search subdirectories
            
        Returns:
            Aggregated results of all API calls
            
        Raises:
            ApiError: On API-related errors
            FileNotFoundError: If directory doesn't exist
        """
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
            
        # Find all matching files
        if recursive:
            pattern_path = f"**/{pattern}"
        else:
            pattern_path = pattern
            
        file_paths = list(directory.glob(pattern_path))
        
        if not file_paths:
            logger.warning("No files matching pattern '%s' found in %s", 
                         pattern, directory)
            return {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
            
        logger.info("Found %d files matching pattern '%s' in %s", 
                   len(file_paths), pattern, directory)
                   
        # Process all files
        return await self.process_files(file_paths, debug)
    
    async def process_large_payload(
        self, 
        payload: Mapping[str, Any],
        debug: bool = False
    ) -> dict[str, Any]:
        """
        Process a large payload by splitting it into smaller batches.
        
        Args:
            payload: Large payload dict to split and send
            debug: Whether to enable debug mode
            
        Returns:
            Aggregated results
            
        Raises:
            ApiError: On API-related errors
            PayloadValidationError: If payload is invalid
        """
        return await self.client.split_and_send(
            payload, 
            batch_size=self.batch_size, 
            debug=debug
        )
    
    async def process_large_file(
        self, 
        file_path: Path,
        debug: bool = False
    ) -> dict[str, Any]:
        """
        Process a large JSON file by splitting its payload into smaller batches.
        
        Args:
            file_path: Path to JSON file containing a large payload
            debug: Whether to enable debug mode
            
        Returns:
            Aggregated results
            
        Raises:
            ApiError: On API-related errors
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
            PayloadValidationError: If payload is invalid
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
                
            logger.info("Processing large file %s with %d detections", 
                       file_path, len(payload.get("data", [])))
                       
            return await self.process_large_payload(payload, debug)
            
        except FileNotFoundError:
            logger.error("File not found: %s", file_path)
            raise
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in file %s: %s", file_path, str(e))
            raise