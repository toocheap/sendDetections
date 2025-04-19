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
from pathlib import Path
from typing import Any, Optional, Sequence, cast
from collections.abc import Mapping

from sendDetections.async_api_client import AsyncApiClient
from sendDetections.csv_converter import CSVConverter
from sendDetections.errors import (
    ApiError, PayloadValidationError, CSVConversionError
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
        max_retries: int = 3
    ):
        """
        Initialize the batch processor.
        
        Args:
            api_token: Recorded Future API token
            api_url: Optional custom API URL
            max_concurrent: Maximum number of concurrent API requests
            batch_size: Maximum number of detections per API request
            max_retries: Maximum number of retry attempts for API errors
        """
        self.api_token = api_token
        self.api_url = api_url
        self.max_concurrent = max_concurrent
        self.batch_size = batch_size
        self.max_retries = max_retries
        
        # Initialize the async API client
        self.client = AsyncApiClient(
            api_token=api_token,
            api_url=api_url,
            max_retries=max_retries,
            max_concurrent=max_concurrent
        )
        
        logger.debug(
            "BatchProcessor initialized with max_concurrent=%d, batch_size=%d",
            max_concurrent, batch_size
        )
    
    async def process_files(
        self, 
        file_paths: Sequence[Path], 
        debug: bool = False
    ) -> dict[str, Any]:
        """
        Process multiple JSON files concurrently.
        
        Args:
            file_paths: Paths to JSON files containing detection payloads
            debug: Whether to enable debug mode
            
        Returns:
            Aggregated results of all API calls
            
        Raises:
            ApiError: On API-related errors
            FileNotFoundError: If any file doesn't exist
            json.JSONDecodeError: If any file contains invalid JSON
        """
        if not file_paths:
            return {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
            
        # Load all payloads first to validate JSON
        payloads = []
        for path in file_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                    payloads.append(payload)
                    logger.debug("Loaded payload from %s with %d detections", 
                               path, len(payload.get("data", [])))
            except FileNotFoundError:
                logger.error("File not found: %s", path)
                raise
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON in file %s: %s", path, str(e))
                raise
        
        # Process all payloads concurrently
        logger.info("Processing %d payload files", len(payloads))
        
        results = await self.client.batch_send(
            payloads, 
            debug=debug,
            return_exceptions=True  # Collect exceptions to report afterwards
        )
        
        # Aggregate results and handle exceptions
        aggregated: dict[str, Any] = {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
        successful = 0
        failed = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Error processing file %s: %s", 
                           file_paths[i], str(result))
                failed += 1
            else:
                successful += 1
                if "summary" in result:
                    summary = result["summary"]
                    aggregated["summary"]["submitted"] += summary.get("submitted", 0)
                    aggregated["summary"]["processed"] += summary.get("processed", 0)
                    aggregated["summary"]["dropped"] += summary.get("dropped", 0)
        
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
        
        return aggregated
    
    async def process_csv_files(
        self, 
        csv_paths: Sequence[Path],
        debug: bool = False,
        encoding: str = "utf-8"
    ) -> dict[str, Any]:
        """
        Convert and process multiple CSV files concurrently.
        
        Args:
            csv_paths: Paths to CSV files to convert and send
            debug: Whether to enable debug mode
            encoding: CSV file encoding
            
        Returns:
            Aggregated results of all API calls
            
        Raises:
            ApiError: On API-related errors
            CSVConversionError: If CSV conversion fails
        """
        if not csv_paths:
            return {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
            
        # Convert all CSV files to payloads
        converter = CSVConverter()
        payloads = []
        
        for path in csv_paths:
            try:
                payload = converter.csv_to_payload(path)
                payloads.append(payload)
                logger.debug("Converted CSV file %s to payload with %d detections", 
                           path, len(payload.get("data", [])))
            except CSVConversionError as e:
                logger.error("Error converting CSV file %s: %s", path, str(e))
                raise
                
        # Process all payloads concurrently
        logger.info("Processing %d converted CSV files", len(payloads))
        
        results = await self.client.batch_send(
            payloads, 
            debug=debug,
            return_exceptions=True
        )
        
        # Aggregate results and handle exceptions
        aggregated: dict[str, Any] = {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
        successful = 0
        failed = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Error processing converted CSV file %s: %s", 
                           csv_paths[i], str(result))
                failed += 1
            else:
                successful += 1
                if "summary" in result:
                    summary = result["summary"]
                    aggregated["summary"]["submitted"] += summary.get("submitted", 0)
                    aggregated["summary"]["processed"] += summary.get("processed", 0)
                    aggregated["summary"]["dropped"] += summary.get("dropped", 0)
        
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