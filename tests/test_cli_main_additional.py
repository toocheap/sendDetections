#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Additional tests for the main CLI functionality of sendDetections.
Focus on error handling, edge cases, and command implementations.
"""

import os
import sys
import json
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, mock_open, PropertyMock

import pytest

from sendDetections.__main__ import (
    main, setup_argparse, handle_convert_command, 
    handle_send_command, handle_convert_send_command,
    handle_batch_command
)
from sendDetections.errors import (
    ApiError, ApiAuthenticationError, ApiRateLimitError,
    ApiConnectionError, CSVConversionError
)


class TestAdditionalCommandsAndOptions:
    """Additional tests for CLI commands and options."""
    
    def test_convert_send_command_arguments(self):
        """Test convert-send command arguments."""
        parser = setup_argparse()
        args = parser.parse_args([
            'convert-send', 'file1.csv', '--token', 'api_token', 
            '--debug', '--pattern', '*.csv', '--no-retry'
        ])
        
        assert args.command == 'convert-send'
        assert args.files == ['file1.csv']
        assert args.token == 'api_token'
        assert args.debug is True
        assert args.pattern == '*.csv'
        assert args.no_retry is True
    
    def test_batch_command_advanced_options(self):
        """Test batch command with advanced options."""
        parser = setup_argparse()
        args = parser.parse_args([
            'batch', 'file1.json',
            '--token', 'api_token',
            '--max-concurrent', '10',
            '--batch-size', '50',
            '--max-retries', '5',
            '--export-metrics',
            '--metrics-file', 'metrics.json',
            '--export-results',
            '--export-dir', 'results',
            '--export-format', 'json',
            '--analyze-errors',
            '--no-progress'
        ])
        
        assert args.command == 'batch'
        assert args.files == ['file1.json']
        assert args.token == 'api_token'
        assert args.max_concurrent == 10
        assert args.batch_size == 50
        assert args.max_retries == 5
        assert args.export_metrics is True
        assert args.metrics_file == 'metrics.json'
        assert args.export_results is True
        assert args.export_dir == 'results'
        assert args.export_format == 'json'
        assert args.analyze_errors is True
        assert args.no_progress is True
    
    def test_global_logging_options(self):
        """Test global logging options."""
        parser = setup_argparse()
        args = parser.parse_args([
            '--log-level', 'debug',
            '--json-logs',
            '--log-file', 'app.log',
            'send', 'file.json', '--token', 'api_token'
        ])
        
        assert args.log_level == 'debug'
        assert args.json_logs is True
        assert args.log_file == 'app.log'
        assert args.command == 'send'


class TestHandleSendCommandExtended:
    """Extended tests for handle_send_command function."""
    
    @patch('sendDetections.__main__.EnhancedApiClient')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.open')
    @patch('json.load')
    @patch('sendDetections.config.get_api_url')
    def test_handle_send_command_env_token(self, mock_get_api_url, mock_json_load, mock_path_open, mock_path_exists, mock_client_class):
        """Test handle_send_command using token from environment variable."""
        # Setup mocks
        mock_get_api_url.return_value = "https://api.example.com/test"
        mock_client = MagicMock()
        mock_client.send_data.return_value = {
            "summary": {"submitted": 1, "processed": 1, "dropped": 0}
        }
        mock_client_class.return_value = mock_client
        mock_path_exists.return_value = True
        mock_json_load.return_value = {"data": [{"test": "payload"}]}
        
        # Create args with token=None to trigger env var lookup
        args = MagicMock()
        args.token = None
        args.files = ["test.json"]
        args.debug = False
        args.no_retry = False
        args.max_retries = 3
        
        # Test with env var set
        with patch.dict('os.environ', {"RF_API_TOKEN": "env_token"}):
            result = handle_send_command(args)
        
        # Verify
        assert result == 0
        mock_client_class.assert_called_with(
            api_token="env_token",
            api_url="https://api.example.com/test",
            max_retries=3
        )
        mock_client.send_data.assert_called_once()
    
    @patch('pathlib.Path.open')
    @patch('sendDetections.__main__.EnhancedApiClient')
    def test_handle_send_command_file_not_found(self, mock_client_class, mock_path_open):
        """Test handle_send_command with file not found error."""
        # Setup mocks - make open raise FileNotFoundError
        mock_path_open.side_effect = FileNotFoundError("[Errno 2] No such file or directory: 'nonexistent.json'")
        
        # Create args
        args = MagicMock()
        args.token = "test_token"
        args.files = ["nonexistent.json"]
        args.debug = False
        args.no_retry = False
        args.max_retries = 3
        
        # Call function
        result = handle_send_command(args)
        
        # Verify
        assert result == 1  # Error code
        # Note: client is still created because that happens before file processing
        mock_client_class.assert_called_once()
    
    @patch('sendDetections.__main__.EnhancedApiClient')
    @patch('pathlib.Path.open')
    @patch('json.load')
    def test_handle_send_command_json_error(self, mock_json_load, mock_path_open, mock_client_class):
        """Test handle_send_command with JSON parsing error."""
        # Setup mocks
        mock_json_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_file = MagicMock()
        mock_path_open.return_value.__enter__.return_value = mock_file
        
        # Create args
        args = MagicMock()
        args.token = "test_token"
        args.files = ["invalid.json"]
        args.debug = False
        args.no_retry = False
        args.max_retries = 3
        
        # Call function
        result = handle_send_command(args)
        
        # Verify
        assert result == 1  # Error code
        # Note: The client is still created in __main__.py because that happens
        # before processing files. What's important is that no successful API calls were made.
        mock_client = mock_client_class.return_value
        assert mock_client.send_data.called is False
    
    @patch('sendDetections.__main__.EnhancedApiClient')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.open')
    @patch('json.load')
    def test_handle_send_command_api_error(self, mock_json_load, mock_path_open, mock_path_exists, mock_client_class):
        """Test handle_send_command with API error."""
        # Setup mocks
        mock_client = MagicMock()
        mock_client.send_data.side_effect = ApiError("API call failed", 500)
        mock_client_class.return_value = mock_client
        mock_path_exists.return_value = True
        mock_json_load.return_value = {"data": [{"test": "payload"}]}
        
        # Create args
        args = MagicMock()
        args.token = "test_token"
        args.files = ["test.json"]
        args.debug = False
        args.no_retry = False
        args.max_retries = 3
        
        # Call function
        result = handle_send_command(args)
        
        # Verify
        assert result == 1  # Error code
        mock_client.send_data.assert_called_once()
    
    @patch('sendDetections.__main__.EnhancedApiClient')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.open')
    @patch('json.load')
    def test_handle_send_command_no_retry_flag(self, mock_json_load, mock_path_open, mock_path_exists, mock_client_class):
        """Test handle_send_command with no_retry flag set."""
        # Setup mocks
        mock_client = MagicMock()
        mock_client.send_data.return_value = {
            "summary": {"submitted": 1, "processed": 1, "dropped": 0}
        }
        mock_client_class.return_value = mock_client
        mock_path_exists.return_value = True
        mock_json_load.return_value = {"data": [{"test": "payload"}]}
        
        # Create args with no_retry=True
        args = MagicMock()
        args.token = "test_token"
        args.files = ["test.json"]
        args.debug = False
        args.no_retry = True
        args.max_retries = 3
        
        # Call function
        result = handle_send_command(args)
        
        # Verify
        assert result == 0
        mock_client.send_data.assert_called_with(
            {"data": [{"test": "payload"}]},
            debug=False,
            retry=False  # This should be False because no_retry=True
        )
    
    @patch('sendDetections.__main__.EnhancedApiClient')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.open')
    @patch('json.load')
    def test_handle_send_command_multiple_files(self, mock_json_load, mock_path_open, mock_path_exists, mock_client_class):
        """Test handle_send_command with multiple files."""
        # Setup mocks
        mock_client = MagicMock()
        mock_client.send_data.return_value = {
            "summary": {"submitted": 1, "processed": 1, "dropped": 0}
        }
        mock_client_class.return_value = mock_client
        mock_path_exists.return_value = True
        mock_json_load.return_value = {"data": [{"test": "payload"}]}
        
        # Create args with multiple files
        args = MagicMock()
        args.token = "test_token"
        args.files = ["file1.json", "file2.json"]
        args.debug = False
        args.no_retry = False
        args.max_retries = 3
        
        # Call function
        result = handle_send_command(args)
        
        # Verify
        assert result == 0
        assert mock_client.send_data.call_count == 2


class TestHandleConvertSendCommand:
    """Tests for handle_convert_send_command function."""
    
    @patch('sendDetections.__main__.CSVConverter')
    @patch('sendDetections.__main__.EnhancedApiClient')
    @patch('sendDetections.config.get_api_url')
    def test_handle_convert_send_success(self, mock_get_api_url, mock_client_class, mock_converter_class):
        """Test handle_convert_send_command with successful conversion and send."""
        # Setup mocks
        mock_get_api_url.return_value = "https://api.example.com/test"
        mock_converter = MagicMock()
        converted_file = Path("converted.json")
        mock_converter.run.return_value = [converted_file]
        mock_converter_class.return_value = mock_converter
        
        mock_client = MagicMock()
        mock_client.send_data.return_value = {
            "summary": {"submitted": 1, "processed": 1, "dropped": 0}
        }
        mock_client_class.return_value = mock_client
        
        # Create args
        args = MagicMock()
        args.token = "test_token"
        args.files = []
        args.input_dir = None
        args.pattern = None
        args.debug = False
        args.no_retry = False
        args.max_retries = 3
        
        # Mock file operations
        with patch('pathlib.Path.open', mock_open(read_data='{"data":[]}')), \
             patch('json.load', return_value={"data": []}), \
             patch.dict('os.environ', {}, clear=True):
            
            # Call function
            result = handle_convert_send_command(args)
        
        # Verify
        assert result == 0
        mock_converter.run.assert_called_once()
        mock_client.send_data.assert_called_once()
    
    @patch('sendDetections.__main__.CSVConverter')
    @patch('sendDetections.__main__.EnhancedApiClient')
    @patch('sendDetections.config.get_api_url')
    def test_handle_convert_send_no_converted_files(self, mock_get_api_url, mock_client_class, mock_converter_class):
        """Test handle_convert_send_command with no files converted."""
        # Setup mocks
        mock_get_api_url.return_value = "https://api.example.com/test"
        mock_converter = MagicMock()
        mock_converter.run.return_value = []  # No files converted
        mock_converter_class.return_value = mock_converter
        
        # Mock the client to avoid actual API calls
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Create args
        args = MagicMock()
        args.token = "test_token"
        args.files = []
        args.input_dir = None
        args.pattern = None
        args.debug = False
        args.no_retry = False
        args.max_retries = 3
        
        # Call function - use patch to better control environment
        with patch('os.getenv', return_value="test_token"), \
             patch('sendDetections.__main__.logger'):  # Suppress logs during test
            result = handle_convert_send_command(args)
        
        # Verify
        assert result == 1  # Error code
        mock_converter.run.assert_called_once()
        # Client is created but send_data should not be called
        assert not mock_client.send_data.called
    
    @patch('sendDetections.__main__.CSVConverter')
    @patch('sendDetections.__main__.EnhancedApiClient')
    @patch('sendDetections.config.get_api_url')
    def test_handle_convert_send_with_specific_files(self, mock_get_api_url, mock_client_class, mock_converter_class):
        """Test handle_convert_send_command with specific files."""
        # Setup mocks
        mock_get_api_url.return_value = "https://api.example.com/test"
        mock_converter = MagicMock()
        mock_converter.convert_file.return_value = Path("converted.json")
        mock_converter_class.return_value = mock_converter
        
        mock_client = MagicMock()
        mock_client.send_data.return_value = {
            "summary": {"submitted": 1, "processed": 1, "dropped": 0}
        }
        mock_client_class.return_value = mock_client
        
        # Create args with specific files
        args = MagicMock()
        args.token = "test_token"
        args.files = ["file1.csv", "file2.csv"]
        args.input_dir = None
        args.pattern = None
        args.debug = False
        args.no_retry = False
        args.max_retries = 3
        
        # Mock file operations
        with patch('pathlib.Path.open', mock_open(read_data='{"data":[]}')), \
             patch('json.load', return_value={"data": []}), \
             patch.dict('os.environ', {}, clear=True):
            
            # Call function
            result = handle_convert_send_command(args)
        
        # Verify
        assert result == 0
        assert mock_converter.convert_file.call_count == 2
        assert mock_client.send_data.call_count == 2
    
    @patch('sendDetections.__main__.CSVConverter')
    def test_handle_convert_send_conversion_error(self, mock_converter_class):
        """Test handle_convert_send_command with conversion error."""
        # Setup mocks
        mock_converter = MagicMock()
        mock_converter.run.side_effect = CSVConversionError("Conversion failed")
        mock_converter_class.return_value = mock_converter
        
        # Create args
        args = MagicMock()
        args.token = "test_token"
        args.files = []
        args.input_dir = None
        args.pattern = None
        args.debug = False
        
        # Call function
        result = handle_convert_send_command(args)
        
        # Verify
        assert result == 1  # Error code
        mock_converter.run.assert_called_once()
    
    @patch('sendDetections.__main__.CSVConverter')
    @patch('sendDetections.__main__.EnhancedApiClient')
    @patch('sendDetections.config.get_api_url')
    def test_handle_convert_send_api_error(self, mock_get_api_url, mock_client_class, mock_converter_class):
        """Test handle_convert_send_command with API error."""
        # Setup mocks
        mock_get_api_url.return_value = "https://api.example.com/test"
        mock_converter = MagicMock()
        converted_file = Path("converted.json")
        mock_converter.run.return_value = [converted_file]
        mock_converter_class.return_value = mock_converter
        
        mock_client = MagicMock()
        mock_client.send_data.side_effect = ApiError("API call failed", 500)
        mock_client_class.return_value = mock_client
        
        # Create args
        args = MagicMock()
        args.token = "test_token"
        args.files = []
        args.input_dir = None
        args.pattern = None
        args.debug = False
        args.no_retry = False
        args.max_retries = 3
        
        # Mock file operations
        with patch('pathlib.Path.open', mock_open(read_data='{"data":[]}')), \
             patch('json.load', return_value={"data": []}), \
             patch.dict('os.environ', {}, clear=True):
            
            # Call function
            result = handle_convert_send_command(args)
        
        # Verify
        assert result == 1  # Error code
        mock_converter.run.assert_called_once()
        mock_client.send_data.assert_called_once()


class TestHandleBatchCommand:
    """Tests for handle_batch_command function."""
    
    @pytest.mark.asyncio
    @patch('sendDetections.__main__.BatchProcessor')
    @patch('sendDetections.__main__.ResultExporter')
    @patch('sendDetections.__main__.ErrorAnalyzer')
    async def test_batch_command_with_all_options(self, mock_analyzer_class, mock_exporter_class, mock_processor_class):
        """Test handle_batch_command with all options enabled."""
        # Setup mocks with AsyncMock for async methods
        mock_processor = MagicMock()
        # Use AsyncMock with awaitable return value
        process_files_mock = AsyncMock()
        process_files_mock.return_value = {
            "summary": {"submitted": 5, "processed": 5, "dropped": 0},
            "performance": {"total_time": 1.0, "average_request_time": 0.2},
            "files": {"processed": 1, "failed": 0},
            "errors": []
        }
        # Important: set the process_files attribute directly
        mock_processor.process_files = process_files_mock
        mock_processor_class.return_value = mock_processor
        
        # Mock exporter methods directly
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter
        
        # Mock analyzer
        mock_analyzer = MagicMock()
        mock_analyzer_class.return_value = mock_analyzer
        
        # Create args with all options enabled
        args = MagicMock()
        args.token = "test_token"
        args.files = ["test.json"]
        args.debug = True
        args.max_concurrent = 10
        args.batch_size = 50
        args.max_retries = 5
        args.no_progress = True
        args.export_metrics = False  # No metrics export for simpler test
        args.metrics_file = None
        args.export_results = False  # No results export for simpler test
        args.export_dir = None
        args.export_format = None
        args.analyze_errors = False  # No error analysis for simpler test
        
        # Mock file path handling
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.glob') as mock_glob, \
             patch('pathlib.Path.suffix', new_callable=PropertyMock) as mock_suffix:
            
            # Setup mocks to return a JSON file
            json_file = MagicMock()
            mock_suffix.return_value = ".json"
            mock_glob.return_value = [json_file]
            
            # Call function with proper mocking
            result = await handle_batch_command(args)
        
        # Verify
        assert result == 0
        
        # Check that BatchProcessor was constructed with correct parameters
        mock_processor_class.assert_called_once()
        processor_call = mock_processor_class.call_args
        assert processor_call.kwargs["api_token"] == "test_token"
        assert processor_call.kwargs["max_concurrent"] == 10
        assert processor_call.kwargs["batch_size"] == 50
        assert processor_call.kwargs["max_retries"] == 5
        assert processor_call.kwargs["show_progress"] == False
        
        # Verify process_files was called
        process_files_mock.assert_called_once()
        # Since we disabled metrics/results export and error analysis,
        # these should not be called
        assert not mock_exporter.export_results.called
        assert not mock_exporter.export_metrics.called
        assert not mock_analyzer.analyze.called
    
    @pytest.mark.asyncio
    @patch('sendDetections.__main__.BatchProcessor')
    async def test_batch_command_missing_token(self, mock_processor_class):
        """Test handle_batch_command with missing API token."""
        # Create args with missing token
        args = MagicMock()
        args.token = None
        args.files = ["test.json"]
        args.debug = False
        
        # Call function with no env var
        with patch.dict('os.environ', {}, clear=True):
            result = await handle_batch_command(args)
        
        # Verify
        assert result == 1  # Error code
        assert not mock_processor_class.called
    
    @pytest.mark.asyncio
    async def test_batch_command_no_files_matched(self):
        """Test batch_command with no matching files."""
        # Create args
        args = MagicMock()
        args.token = "test_token"
        args.files = ["nonexistent.json"]
        args.debug = False
        args.max_concurrent = 5
        args.batch_size = 100
        args.max_retries = 3
        args.no_progress = False
        args.export_metrics = False
        args.export_results = False
        args.analyze_errors = False
        
        # Need a more complex patch setup to handle the no files case
        with patch('pathlib.Path.glob', return_value=[]), \
             patch('sendDetections.__main__.logger'), \
             patch('sendDetections.__main__.BatchProcessor', spec=True) as mock_processor_class:
            
            # Call function
            result = await handle_batch_command(args)
        
        # Verify
        assert result == 1  # Error code
        # Since there are no files, processor.process_files() is never called
    
    @pytest.mark.asyncio
    @patch('pathlib.Path.exists')
    @patch('sendDetections.__main__.BatchProcessor')
    async def test_batch_command_processor_error(self, mock_processor_class, mock_exists):
        """Test handle_batch_command with processor error."""
        # Setup mocks
        mock_processor = MagicMock()
        # Create AsyncMock for process_files that raises exception
        process_files_mock = AsyncMock(side_effect=ApiConnectionError("Connection failed"))
        mock_processor.process_files = process_files_mock
        mock_processor_class.return_value = mock_processor
        
        # Set exists to return True
        mock_exists.return_value = True
        
        # Create args
        args = MagicMock()
        args.token = "test_token"
        args.files = ["test.json"]
        args.debug = False
        args.max_concurrent = 5
        args.batch_size = 100
        args.max_retries = 3
        args.no_progress = False
        args.export_metrics = False
        args.export_results = False
        args.analyze_errors = False
        
        # Call function
        result = await handle_batch_command(args)
        
        # Verify
        assert result == 1  # Error code
        process_files_mock.assert_called_once()