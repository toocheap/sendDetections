#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the performance monitoring functionality.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

from sendDetections.performance import (
    PerformanceMetrics, 
    measure_time, 
    async_measure_time, 
    timed_function,
    async_timed_function,
    process_with_progress,
    process_in_batches
)


class TestPerformanceMetrics:
    """Tests for the PerformanceMetrics class."""
    
    def test_initialization(self):
        """Test metrics initialization with default values."""
        metrics = PerformanceMetrics()
        assert metrics.api_calls == 0
        assert metrics.success_calls == 0
        assert metrics.failed_calls == 0
        assert metrics.total_time == 0.0
        assert metrics.min_time == float('inf')
        assert metrics.max_time == 0.0
        assert metrics.avg_time == 0.0
        assert metrics.start_time is None
        assert metrics.end_time is None
        assert metrics.errors_by_type == {}
    
    def test_start_end(self):
        """Test start and end time recording."""
        metrics = PerformanceMetrics()
        
        # Test start
        metrics.start()
        assert metrics.start_time is not None
        assert isinstance(metrics.start_time, datetime)
        
        # Test end
        time.sleep(0.01)  # Small delay to ensure time difference
        metrics.end()
        assert metrics.end_time is not None
        assert isinstance(metrics.end_time, datetime)
        assert metrics.total_time > 0
        assert metrics.end_time > metrics.start_time
    
    def test_record_api_call(self):
        """Test recording API call metrics."""
        metrics = PerformanceMetrics()
        
        # Record successful call
        metrics.record_api_call(0.5, True)
        assert metrics.api_calls == 1
        assert metrics.success_calls == 1
        assert metrics.failed_calls == 0
        assert metrics.min_time == 0.5
        assert metrics.max_time == 0.5
        
        # Record failed call
        metrics.record_api_call(0.3, False)
        assert metrics.api_calls == 2
        assert metrics.success_calls == 1
        assert metrics.failed_calls == 1
        assert metrics.min_time == 0.5  # Unchanged because only successful calls update min/max
        assert metrics.max_time == 0.5
        
        # Record another successful call
        metrics.record_api_call(0.7, True)
        assert metrics.api_calls == 3
        assert metrics.success_calls == 2
        assert metrics.failed_calls == 1
        assert metrics.min_time == 0.5
        assert metrics.max_time == 0.7
    
    def test_record_batch_size(self):
        """Test recording batch sizes for optimization."""
        metrics = PerformanceMetrics()
        
        # Record with batch size
        metrics.record_api_call(0.5, True, batch_size=100)
        metrics.record_api_call(0.6, True, batch_size=150)
        metrics.record_api_call(0.7, True, batch_size=200)
        
        # End metrics to calculate optimal batch size
        metrics.start()
        metrics.end()
        
        assert len(metrics.batch_sizes) == 3
        assert metrics.batch_sizes == [100, 150, 200]
        assert metrics.optimal_batch_size == 150  # Average of batch sizes
    
    def test_record_entities(self):
        """Test recording processed entities count."""
        metrics = PerformanceMetrics()
        
        metrics.record_entities(10)
        assert metrics.entities_processed == 10
        
        metrics.record_entities(20)
        assert metrics.entities_processed == 30
    
    def test_record_error(self):
        """Test recording errors by type."""
        metrics = PerformanceMetrics()
        
        metrics.record_error("ApiError")
        assert metrics.errors_by_type["ApiError"] == 1
        
        metrics.record_error("ApiError")
        assert metrics.errors_by_type["ApiError"] == 2
        
        metrics.record_error("ValidationError")
        assert metrics.errors_by_type["ValidationError"] == 1
        assert len(metrics.errors_by_type) == 2
    
    def test_get_summary(self):
        """Test generating a summary of performance metrics."""
        metrics = PerformanceMetrics()
        metrics.start()
        
        # Record some test data
        metrics.record_api_call(0.5, True, batch_size=100)
        metrics.record_api_call(0.3, False)
        metrics.record_entities(50)
        metrics.record_error("TestError")
        
        time.sleep(0.01)
        metrics.end()
        
        summary = metrics.get_summary()
        
        # Verify structure and content
        assert "api_calls" in summary
        assert summary["api_calls"]["total"] == 2
        assert summary["api_calls"]["success"] == 1
        assert summary["api_calls"]["failed"] == 1
        
        assert "time" in summary
        assert summary["time"]["total_seconds"] > 0
        
        assert "throughput" in summary
        assert summary["throughput"]["entities_processed"] == 50
        
        assert "batching" in summary
        assert summary["batching"]["batch_count"] == 1
        
        assert "errors" in summary
        assert summary["errors"]["TestError"] == 1


class TestTimingUtilities:
    """Tests for the timing utility functions."""
    
    def test_measure_time(self):
        """Test the measure_time context manager."""
        with measure_time() as result:
            time.sleep(0.01)
        
        assert "start_time" in result
        assert "end_time" in result
        assert "duration" in result
        assert result["duration"] >= 0.01
    
    @pytest.mark.asyncio
    async def test_async_measure_time(self):
        """Test the async_measure_time function."""
        async def dummy_coroutine():
            await asyncio.sleep(0.01)
            return "result"
        
        result, duration = await async_measure_time(dummy_coroutine())
        
        assert result == "result"
        assert duration >= 0.01
    
    def test_timed_function_decorator(self):
        """Test the timed_function decorator."""
        @timed_function
        def dummy_function(x, y):
            time.sleep(0.01)
            return x + y
        
        # Test that the function works correctly and returns the expected result
        result = dummy_function(1, 2)
        assert result == 3
        
        # We don't test the logging since it's implementation-specific and would require 
        # complex mocking of the logger module which isn't the focus of this test
    
    @pytest.mark.asyncio
    async def test_async_timed_function_decorator(self):
        """Test the async_timed_function decorator."""
        @async_timed_function
        async def dummy_async_function(x, y):
            await asyncio.sleep(0.01)
            return x + y
        
        # Test that the async function works correctly and returns the expected result
        result = await dummy_async_function(1, 2)
        assert result == 3
        
        # We don't test the logging since it's implementation-specific and would require 
        # complex mocking of the logger module which isn't the focus of this test


@pytest.mark.asyncio
async def test_process_with_progress():
    """Test processing items with progress tracking."""
    items = [1, 2, 3, 4, 5]
    
    async def process_item(item):
        await asyncio.sleep(0.01)
        return item * 2
    
    # Test with disabled progress bar to avoid output in tests
    results = await process_with_progress(
        items, 
        process_item, 
        ascii=True,  # Use ASCII to avoid encoding issues
        leave=False,  # Don't leave progress bar
        max_concurrency=2  # Limit concurrency
    )
    
    assert len(results) == 5
    assert sorted(results) == [2, 4, 6, 8, 10]


@pytest.mark.asyncio
async def test_process_in_batches():
    """Test processing items in batches with progress tracking."""
    items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    
    async def process_batch(batch):
        await asyncio.sleep(0.01)
        return [item * 2 for item in batch]
    
    # Test with disabled progress bar to avoid output in tests
    results = await process_in_batches(
        items, 
        batch_size=3, 
        process_batch_func=process_batch,
        ascii=True,  # Use ASCII to avoid encoding issues
        leave=False  # Don't leave progress bar
    )
    
    assert len(results) == 10
    assert results == [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]