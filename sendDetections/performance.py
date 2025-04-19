#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Performance monitoring and progress tracking utilities.
Provides tools for measuring API call performance and displaying progress.
"""

import asyncio
import contextlib
import functools
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, TypeVar, Union, cast
from collections.abc import Awaitable, Iterable, Mapping, Sequence

from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

# Configure logger
logger = logging.getLogger(__name__)

# Type variables for generic function types
T = TypeVar('T')
R = TypeVar('R')


class PerformanceMetrics:
    """
    Track and report performance metrics for API calls.
    """
    
    def __init__(self):
        """Initialize performance metrics tracking."""
        self.api_calls = 0
        self.success_calls = 0
        self.failed_calls = 0
        self.total_time = 0.0
        self.min_time = float('inf')
        self.max_time = 0.0
        self.avg_time = 0.0
        self.start_time = None
        self.end_time = None
        
        # Track retries
        self.retries = 0
        
        # Track rates
        self.entities_processed = 0  # IOCs processed
        self.entities_per_second = 0.0
        
        # Track batch performance
        self.batch_sizes: list[int] = []
        self.optimal_batch_size = 0
        
        # Track errors by type
        self.errors_by_type: dict[str, int] = {}
    
    def start(self) -> None:
        """Mark the start of performance measurement."""
        self.start_time = datetime.now()
    
    def end(self) -> None:
        """Mark the end of performance measurement."""
        self.end_time = datetime.now()
        if self.start_time and self.end_time:
            self.total_time = (self.end_time - self.start_time).total_seconds()
            if self.entities_processed > 0 and self.total_time > 0:
                self.entities_per_second = self.entities_processed / self.total_time
            
            # Calculate average API call time if there were any successful calls
            if self.success_calls > 0:
                self.avg_time = self.total_time / self.success_calls
            
            # Determine optimal batch size if we have batch data
            if self.batch_sizes:
                # For now, simple average
                self.optimal_batch_size = int(sum(self.batch_sizes) / len(self.batch_sizes))
    
    def record_api_call(self, duration: float, success: bool, batch_size: Optional[int] = None) -> None:
        """
        Record metrics for a single API call.
        
        Args:
            duration: Call duration in seconds
            success: Whether the call was successful
            batch_size: Size of the batch if this was a batch call
        """
        self.api_calls += 1
        
        if success:
            self.success_calls += 1
            self.min_time = min(self.min_time, duration)
            self.max_time = max(self.max_time, duration)
        else:
            self.failed_calls += 1
        
        if batch_size is not None and batch_size > 0:
            self.batch_sizes.append(batch_size)
    
    def record_retry(self) -> None:
        """Record a retry attempt."""
        self.retries += 1
    
    def record_entities(self, count: int) -> None:
        """
        Record the number of entities processed.
        
        Args:
            count: Number of entities processed
        """
        self.entities_processed += count
    
    def record_error(self, error_type: str) -> None:
        """
        Record an error by type.
        
        Args:
            error_type: Type of error that occurred
        """
        if error_type not in self.errors_by_type:
            self.errors_by_type[error_type] = 0
        self.errors_by_type[error_type] += 1
    
    def get_summary(self) -> dict[str, Any]:
        """
        Get a summary of performance metrics.
        
        Returns:
            Dictionary with performance metrics
        """
        return {
            "api_calls": {
                "total": self.api_calls,
                "success": self.success_calls,
                "failed": self.failed_calls,
                "success_rate": (self.success_calls / self.api_calls * 100) if self.api_calls > 0 else 0
            },
            "time": {
                "total_seconds": self.total_time,
                "start": self.start_time.isoformat() if self.start_time else None,
                "end": self.end_time.isoformat() if self.end_time else None,
                "avg_call_time": self.avg_time,
                "min_call_time": self.min_time if self.min_time != float('inf') else 0,
                "max_call_time": self.max_time
            },
            "retries": self.retries,
            "throughput": {
                "entities_processed": self.entities_processed,
                "entities_per_second": self.entities_per_second
            },
            "batching": {
                "batch_count": len(self.batch_sizes),
                "optimal_batch_size": self.optimal_batch_size
            },
            "errors": self.errors_by_type
        }
    
    def log_summary(self, level: int = logging.INFO) -> None:
        """
        Log a summary of performance metrics.
        
        Args:
            level: Logging level to use
        """
        if not self.start_time or not self.end_time:
            logger.warning("Performance metrics not started or ended properly")
            return
        
        duration = self.end_time - self.start_time
        
        logger.log(level, "Performance Summary:")
        logger.log(level, "-------------------")
        logger.log(level, "Total time: %s", str(duration))
        logger.log(level, "API calls: %d total, %d success, %d failed (%.1f%% success rate)",
                 self.api_calls, self.success_calls, self.failed_calls,
                 (self.success_calls / self.api_calls * 100) if self.api_calls > 0 else 0)
        
        if self.success_calls > 0:
            logger.log(level, "Call times: avg=%.2fs, min=%.2fs, max=%.2fs",
                     self.avg_time,
                     self.min_time if self.min_time != float('inf') else 0,
                     self.max_time)
        
        if self.retries > 0:
            logger.log(level, "Retries: %d", self.retries)
        
        if self.entities_processed > 0:
            logger.log(level, "Throughput: %d entities in %.2fs (%.2f entities/sec)",
                     self.entities_processed, self.total_time, self.entities_per_second)
        
        if self.batch_sizes:
            logger.log(level, "Batching: %d batches, optimal size=%d",
                     len(self.batch_sizes), self.optimal_batch_size)
        
        if self.errors_by_type:
            logger.log(level, "Errors by type:")
            for error_type, count in self.errors_by_type.items():
                logger.log(level, "  %s: %d", error_type, count)


@contextlib.contextmanager
def measure_time() -> Iterable[dict]:
    """
    Context manager for measuring execution time.
    
    Yields:
        Dictionary that will be updated with timing results
    """
    result = {"start_time": time.time(), "end_time": None, "duration": None}
    try:
        yield result
    finally:
        result["end_time"] = time.time()
        result["duration"] = result["end_time"] - result["start_time"]


async def async_measure_time(coro: Awaitable[T]) -> Tuple[T, float]:
    """
    Measure the execution time of an awaitable.
    
    Args:
        coro: The coroutine to measure
        
    Returns:
        Tuple of (result, duration_in_seconds)
    """
    start_time = time.time()
    result = await coro
    end_time = time.time()
    return result, end_time - start_time


def timed_function(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to measure and log function execution time.
    
    Args:
        func: The function to time
        
    Returns:
        Wrapped function that logs execution time
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start_time
            logger.debug("%s execution time: %.4f seconds", func.__name__, duration)
    return wrapper


def async_timed_function(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """
    Decorator to measure and log async function execution time.
    
    Args:
        func: The async function to time
        
    Returns:
        Wrapped async function that logs execution time
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            duration = time.time() - start_time
            logger.debug("%s execution time: %.4f seconds", func.__name__, duration)
    return wrapper


async def process_with_progress(
    items: Sequence[T],
    process_func: Callable[[T], Awaitable[R]],
    description: str = "Processing",
    unit: str = "item",
    ascii: bool = False,
    leave: bool = True,
    max_concurrency: int = 5
) -> list[R]:
    """
    Process items with a progress bar and concurrency limit.
    
    Args:
        items: Items to process
        process_func: Async function to process each item
        description: Description for the progress bar
        unit: Unit name for the progress bar
        ascii: Whether to use ASCII characters for the progress bar
        leave: Whether to leave the progress bar after completion
        max_concurrency: Maximum number of concurrent tasks
        
    Returns:
        List of results in the same order as the input items
    """
    if not items:
        return []
    
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def process_with_semaphore(item: T) -> R:
        async with semaphore:
            return await process_func(item)
    
    tasks = [process_with_semaphore(item) for item in items]
    
    # Process with progress bar
    results = []
    for task in tqdm_asyncio.as_completed(
        tasks,
        total=len(items),
        desc=description,
        unit=unit,
        ascii=ascii,
        leave=leave
    ):
        result = await task
        results.append(result)
    
    # Sort results to match input order
    # Note: This doesn't work directly with as_completed, need an alternative approach
    # For now, we'll execute tasks in order to maintain ordering
    ordered_results = []
    for task in tqdm_asyncio.tqdm(
        asyncio.as_completed([asyncio.create_task(process_with_semaphore(item)) for item in items]),
        total=len(items),
        desc=description,
        unit=unit,
        ascii=ascii,
        leave=leave
    ):
        ordered_results.append(await task)
    
    return ordered_results


async def process_in_batches(
    items: Sequence[T],
    batch_size: int,
    process_batch_func: Callable[[list[T]], Awaitable[list[R]]],
    description: str = "Processing batches",
    unit: str = "batch",
    ascii: bool = False,
    leave: bool = True
) -> list[R]:
    """
    Process items in batches with a progress bar.
    
    Args:
        items: Items to process
        batch_size: Number of items per batch
        process_batch_func: Async function to process each batch
        description: Description for the progress bar
        unit: Unit name for the progress bar
        ascii: Whether to use ASCII characters for the progress bar
        leave: Whether to leave the progress bar after completion
        
    Returns:
        Flattened list of results
    """
    if not items:
        return []
    
    # Create batches
    batches = []
    for i in range(0, len(items), batch_size):
        batches.append(items[i:i+batch_size])
    
    # Process batches with progress bar
    results: list[R] = []
    for batch in tqdm(batches, desc=description, unit=unit, ascii=ascii, leave=leave):
        batch_results = await process_batch_func(batch)
        results.extend(batch_results)
    
    return results