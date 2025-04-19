#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the submit command functionality of sendDetections.
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock

import pytest

from sendDetections.__main__ import (
    main, setup_argparse, handle_submit_command
)
from sendDetections.errors import (
    ApiError, ApiAuthenticationError, ApiRateLimitError,
    ApiConnectionError, CSVConversionError
)


class TestSubmitCommand:
    """Tests for submit command arguments and processing."""
    
    def test_file_arguments_with_options(self):
        """Test file arguments with various options."""
        parser = setup_argparse()
        args = parser.parse_args([
            'file1.csv', 'file2.json',
            '--token', 'api_token',
            '--debug',
            '--concurrent', '10',
            '--batch-size', '50',
            '--max-retries', '5',
            '--export-metrics',
            '--metrics-file', 'metrics.json',
            '--export-results',
            '--export-dir', 'results',
            '--export-format', 'json',
            '--analyze-errors',
            '--no-progress',
            '--org-id', 'uhash:T2j9L'
        ])
        
        assert args.files == ['file1.csv', 'file2.json']
        assert args.token == 'api_token'
        assert args.debug is True
        assert args.concurrent == 10
        assert args.batch_size == 50
        assert args.max_retries == 5
        assert args.export_metrics is True
        assert args.metrics_file == 'metrics.json'
        assert args.export_results is True
        assert args.export_dir == 'results'
        assert args.export_format == 'json'
        assert args.analyze_errors is True
        assert args.no_progress is True
        assert args.org_id == 'uhash:T2j9L'
    
    def test_empty_arguments(self):
        """Test with no files specified."""
        parser = setup_argparse()
        args = parser.parse_args([])
        
        assert args.files == []


@patch('sendDetections.__main__.configure_logging')
@patch('sendDetections.__main__.handle_submit_command')
@patch('asyncio.run')
def test_main_with_files(mock_asyncio_run, mock_handle_submit, mock_configure_logging):
    """Test main function with file parameters."""
    mock_asyncio_run.return_value = 0
    
    # Mock args to simulate file submission
    mock_args = MagicMock()
    mock_args.files = ['file.csv']
    
    with patch('sys.argv', ['sendDetections', 'file.csv']):
        with patch('sendDetections.__main__.setup_argparse') as mock_parser:
            mock_parser.return_value.parse_args.return_value = mock_args
            exit_code = main()
    
    assert exit_code == 0
    assert mock_asyncio_run.called


@pytest.mark.asyncio
@patch('sendDetections.__main__.BatchProcessor')
async def test_handle_submit_command_success(mock_processor_class):
    """Test handle_submit_command with successful processing."""
    # Setup mocks
    mock_processor = MagicMock()
    
    # Mock the process_files and process_csv_files methods
    mock_processor.process_files = AsyncMock(return_value={
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    })
    mock_processor.process_csv_files = AsyncMock(return_value={
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    })
    
    mock_processor_class.return_value = mock_processor
    
    # Create args with minimal required attributes
    args = MagicMock()
    args.token = "test_token"
    args.files = ["test.csv", "test.json"]
    args.debug = False
    args.concurrent = 5
    args.batch_size = 100
    args.max_retries = 3
    args.no_progress = False
    args.export_metrics = False
    args.export_results = False
    args.analyze_errors = False
    args.input_dir = None
    args.pattern = None
    args.org_id = None
    
    # Patch Path existence and glob to simulate files
    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.glob', return_value=[Path('test.csv'), Path('test.json')]):
            # Call function
            with patch.dict('os.environ', {}, clear=True):
                result = await handle_submit_command(args)
    
    # Verify
    assert result == 0
    mock_processor.process_csv_files.assert_called_once()
    mock_processor.process_files.assert_called_once()
    
    # Verify BatchProcessor was created without organization_id
    mock_processor_class.assert_called_once()
    _, kwargs = mock_processor_class.call_args
    assert 'organization_id' in kwargs
    assert kwargs['organization_id'] is None  # No org_id provided


@pytest.mark.asyncio
@patch('sendDetections.__main__.BatchProcessor')
async def test_handle_submit_command_with_organization_id(mock_processor_class):
    """Test handle_submit_command with organization ID specified via command line."""
    # Setup mocks
    mock_processor = MagicMock()
    
    # Mock the process_files and process_csv_files methods
    mock_processor.process_files = AsyncMock(return_value={
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    })
    mock_processor.process_csv_files = AsyncMock(return_value={
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    })
    
    mock_processor_class.return_value = mock_processor
    
    # Create args with organization ID
    args = MagicMock()
    args.token = "test_token"
    args.files = ["test.json"]
    args.debug = False
    args.concurrent = 5
    args.batch_size = 100
    args.max_retries = 3
    args.no_progress = False
    args.export_metrics = False
    args.export_results = False
    args.analyze_errors = False
    args.input_dir = None
    args.pattern = None
    args.org_id = "uhash:T2j9L"  # Specify organization ID from command line
    
    # Patch Path existence and glob to simulate files
    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.glob', return_value=[Path('test.json')]):
            # Call function
            with patch.dict('os.environ', {}, clear=True):
                # Mock get_config to return None (not from config)
                with patch('sendDetections.config.get_config', return_value=None):
                    result = await handle_submit_command(args)
    
    # Verify
    assert result == 0
    
    # Verify BatchProcessor was created with correct organization_id
    mock_processor_class.assert_called_once()
    _, kwargs = mock_processor_class.call_args
    assert 'organization_id' in kwargs
    assert kwargs['organization_id'] == "uhash:T2j9L"


@pytest.mark.asyncio
@patch('sendDetections.__main__.BatchProcessor')
async def test_handle_submit_command_with_organization_id_from_config(mock_processor_class):
    """Test handle_submit_command with organization ID from configuration."""
    # Setup mocks
    mock_processor = MagicMock()
    
    # Mock the process_files and process_csv_files methods
    mock_processor.process_files = AsyncMock(return_value={
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    })
    
    mock_processor_class.return_value = mock_processor
    
    # Create args without organization ID in command line
    args = MagicMock()
    args.token = "test_token"
    args.files = ["test.json"]
    args.debug = False
    args.concurrent = 5
    args.batch_size = 100
    args.max_retries = 3
    args.no_progress = False
    args.export_metrics = False
    args.export_results = False
    args.analyze_errors = False
    args.input_dir = None
    args.pattern = None
    args.org_id = None  # No organization ID on command line
    
    # Patch Path existence and glob to simulate files
    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.glob', return_value=[Path('test.json')]):
            # Call function
            with patch.dict('os.environ', {}, clear=True):
                # Mock get_config to return organization_id from config
                with patch('sendDetections.config.get_config', 
                           side_effect=lambda key, default=None: "uhash:CONFIG" if key == "organization_id" else None):
                    result = await handle_submit_command(args)
    
    # Verify
    assert result == 0
    
    # Verify BatchProcessor was created with organization_id from config
    mock_processor_class.assert_called_once()
    _, kwargs = mock_processor_class.call_args
    assert 'organization_id' in kwargs
    assert kwargs['organization_id'] == "uhash:CONFIG"  # From config, not command line


@pytest.mark.asyncio
@patch('sendDetections.__main__.BatchProcessor')
async def test_handle_submit_command_organization_id_precedence(mock_processor_class):
    """Test organization ID precedence (command line over config)."""
    # Setup mocks
    mock_processor = MagicMock()
    
    # Mock the process_files method
    mock_processor.process_files = AsyncMock(return_value={
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    })
    
    mock_processor_class.return_value = mock_processor
    
    # Create args with organization ID in command line
    args = MagicMock()
    args.token = "test_token"
    args.files = ["test.json"]
    args.debug = False
    args.concurrent = 5
    args.batch_size = 100
    args.max_retries = 3
    args.no_progress = False
    args.export_metrics = False
    args.export_results = False
    args.analyze_errors = False
    args.input_dir = None
    args.pattern = None
    args.org_id = "uhash:CMDLINE"  # Organization ID from command line
    
    # Patch Path existence and glob to simulate files
    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.glob', return_value=[Path('test.json')]):
            # Call function
            with patch.dict('os.environ', {}, clear=True):
                # Mock get_config to return a DIFFERENT organization_id from config
                with patch('sendDetections.config.get_config', 
                           side_effect=lambda key, default=None: "uhash:CONFIG" if key == "organization_id" else None):
                    result = await handle_submit_command(args)
    
    # Verify
    assert result == 0
    
    # Verify command line takes precedence over config
    mock_processor_class.assert_called_once()
    _, kwargs = mock_processor_class.call_args
    assert 'organization_id' in kwargs
    assert kwargs['organization_id'] == "uhash:CMDLINE"  # Command line value used


@pytest.mark.asyncio
@patch('sendDetections.__main__.BatchProcessor')
async def test_handle_submit_command_no_token(mock_processor_class):
    """Test handle_submit_command with missing API token."""
    # Create args
    args = MagicMock()
    args.token = None
    args.files = ["test.json"]
    
    # Call function
    with patch.dict('os.environ', {}, clear=True):  # Ensure no env vars
        result = await handle_submit_command(args)
    
    # Verify
    assert result == 1  # Error code
    assert not mock_processor_class.called


@pytest.mark.asyncio
@patch('sendDetections.__main__.BatchProcessor')
async def test_handle_submit_command_no_files_found(mock_processor_class):
    """Test handle_submit_command when no matching files are found."""
    # Setup processor mock
    mock_processor = MagicMock()
    mock_processor_class.return_value = mock_processor
    
    # Create args
    args = MagicMock()
    args.token = "test_token"
    args.files = []
    args.input_dir = Path("/test/dir")
    args.pattern = "*.csv"
    
    # Patch Path glob to return empty list (no files found)
    with patch('pathlib.Path.glob', return_value=[]):
        # Call function
        result = await handle_submit_command(args)
    
    # Verify
    assert result == 1  # Error code
    # Processor was created but no processing methods were called
    assert mock_processor_class.called
    assert not mock_processor.process_files.called
    assert not mock_processor.process_csv_files.called


@pytest.mark.asyncio
@patch('sendDetections.__main__.BatchProcessor')
async def test_handle_submit_command_api_error(mock_processor_class):
    """Test handle_submit_command with API error."""
    # Setup mocks
    mock_processor = MagicMock()
    mock_processor.process_files = AsyncMock(side_effect=ApiError("API Error"))
    mock_processor_class.return_value = mock_processor
    
    # Create args
    args = MagicMock()
    args.token = "test_token"
    args.files = ["test.json"]
    args.debug = False
    args.concurrent = 5
    args.batch_size = 100
    args.max_retries = 3
    args.no_progress = False
    args.export_metrics = False
    args.export_results = False
    args.analyze_errors = False
    
    # Patch Path existence and suffix check
    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.suffix', PropertyMock(return_value='.json')):
            # Call function
            result = await handle_submit_command(args)
    
    # Verify
    assert result == 1  # Error code
    assert mock_processor.process_files.called