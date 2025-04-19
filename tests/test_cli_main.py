#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the main CLI functionality of sendDetections.
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from sendDetections.__main__ import (
    main, setup_argparse, handle_convert_command, 
    handle_send_command, handle_convert_send_command,
    handle_batch_command
)


class TestCliSetup:
    """Tests for CLI setup and argument parsing."""
    
    def test_setup_argparse(self):
        """Test argument parser setup."""
        parser = setup_argparse()
        
        # Test that the parser has the expected commands
        # Add required arguments for each command to avoid SystemExit
        args = parser.parse_args(['convert', 'dummy.csv'])
        assert args.command == 'convert'
        
        args = parser.parse_args(['send', 'dummy.json', '--token', 'dummy_token'])
        assert args.command == 'send'
        
        args = parser.parse_args(['convert-send', 'dummy.csv', '--token', 'dummy_token'])
        assert args.command == 'convert-send'
        
        args = parser.parse_args(['batch', 'dummy.json', '--token', 'dummy_token'])
        assert args.command == 'batch'
    
    def test_convert_command_arguments(self):
        """Test convert command arguments."""
        parser = setup_argparse()
        args = parser.parse_args(['convert', 'file1.csv', 'file2.csv'])
        
        assert args.command == 'convert'
        assert args.files == ['file1.csv', 'file2.csv']
        assert args.input_dir is None
        assert args.output_dir is None
        assert args.pattern is None
    
    def test_send_command_arguments(self):
        """Test send command arguments."""
        parser = setup_argparse()
        args = parser.parse_args(['send', 'file1.json', '--token', 'api_token', '--debug'])
        
        assert args.command == 'send'
        assert args.files == ['file1.json']
        assert args.token == 'api_token'
        assert args.debug is True
        assert args.max_retries == 3  # Default value
    
    def test_batch_command_arguments(self):
        """Test batch command arguments."""
        parser = setup_argparse()
        args = parser.parse_args([
            'batch', 'file1.json', 'file2.json',
            '--token', 'api_token',
            '--max-concurrent', '10',
            '--batch-size', '50',
            '--export-results',
            '--export-format', 'json',
            '--analyze-errors'
        ])
        
        assert args.command == 'batch'
        assert args.files == ['file1.json', 'file2.json']
        assert args.token == 'api_token'
        assert args.max_concurrent == 10
        assert args.batch_size == 50
        assert args.export_results is True
        assert args.export_format == 'json'
        assert args.analyze_errors is True


@patch('sys.stderr')  # Silence the error messages during test
def test_main_no_command(mock_stderr):
    """Test main function with no command."""
    with patch('sys.argv', ['sendDetections']):
        with patch('sendDetections.__main__.configure_logging'):
            with patch('sendDetections.__main__.setup_argparse') as mock_parser:
                # Mock the parser to handle the no-command case
                mock_parser.return_value.parse_args.return_value = MagicMock(command=None)
                exit_code = main()
                assert exit_code == 1  # Should return error code


@patch('sys.stderr')  # Silence the error messages during test
def test_main_unknown_command(mock_stderr):
    """Test main function with unknown command."""
    with patch('sys.argv', ['sendDetections', 'unknown']):
        with patch('sendDetections.__main__.configure_logging'):
            with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
                # Simulate the parser recognizing an unknown command
                mock_args = MagicMock()
                mock_args.command = 'unknown'
                mock_parse_args.return_value = mock_args
                
                exit_code = main()
                assert exit_code == 1  # Should return error code


@patch('sendDetections.__main__.configure_logging')
@patch('sendDetections.__main__.handle_convert_command')
def test_main_convert_command(mock_handle_convert, mock_configure_logging):
    """Test main function with convert command."""
    mock_handle_convert.return_value = 0
    
    with patch('sys.argv', ['sendDetections', 'convert']):
        exit_code = main()
        
    assert exit_code == 0
    assert mock_handle_convert.called


@patch('sendDetections.__main__.configure_logging')
@patch('sendDetections.__main__.handle_send_command')
def test_main_send_command(mock_handle_send, mock_configure_logging):
    """Test main function with send command."""
    mock_handle_send.return_value = 0
    
    with patch('sys.argv', ['sendDetections', 'send', 'file.json']):
        exit_code = main()
        
    assert exit_code == 0
    assert mock_handle_send.called


@patch('sendDetections.__main__.configure_logging')
@patch('sendDetections.__main__.handle_convert_send_command')
def test_main_convert_send_command(mock_handle_convert_send, mock_configure_logging):
    """Test main function with convert-send command."""
    mock_handle_convert_send.return_value = 0
    
    with patch('sys.argv', ['sendDetections', 'convert-send']):
        exit_code = main()
        
    assert exit_code == 0
    assert mock_handle_convert_send.called


@patch('sendDetections.__main__.configure_logging')
@patch('sendDetections.__main__.handle_batch_command')
@patch('asyncio.run')
def test_main_batch_command(mock_asyncio_run, mock_handle_batch, mock_configure_logging):
    """Test main function with batch command."""
    mock_asyncio_run.return_value = 0
    
    with patch('sys.argv', ['sendDetections', 'batch', 'file.json']):
        exit_code = main()
        
    assert exit_code == 0
    assert mock_asyncio_run.called


@patch('sendDetections.__main__.CSVConverter')
def test_handle_convert_command_success(mock_converter_class):
    """Test handle_convert_command with successful conversion."""
    # Setup mock
    mock_converter = MagicMock()
    mock_converter.run.return_value = [Path('test_output.json')]
    mock_converter_class.return_value = mock_converter
    
    # Create args
    args = MagicMock()
    args.files = []
    args.input_dir = None
    args.output_dir = None
    args.pattern = None
    
    # Call function
    result = handle_convert_command(args)
    
    # Verify
    assert result == 0
    assert mock_converter.run.called


@patch('sendDetections.__main__.CSVConverter')
def test_handle_convert_command_no_files(mock_converter_class):
    """Test handle_convert_command with no successful conversions."""
    # Setup mock
    mock_converter = MagicMock()
    mock_converter.run.return_value = []  # No files converted
    mock_converter_class.return_value = mock_converter
    
    # Create args
    args = MagicMock()
    args.files = []
    args.input_dir = None
    args.output_dir = None
    args.pattern = None
    
    # Call function
    result = handle_convert_command(args)
    
    # Verify
    assert result == 1  # Error code
    assert mock_converter.run.called


@patch('sendDetections.__main__.EnhancedApiClient')
@patch('pathlib.Path.open')  # Patch pathlib.Path.open instead of builtins.open
@patch('json.load')
def test_handle_send_command_success(mock_json_load, mock_path_open, mock_client_class):
    """Test handle_send_command with successful API call."""
    # Setup mocks
    mock_client = MagicMock()
    mock_client.send_data.return_value = {
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    }
    mock_client_class.return_value = mock_client
    
    # Mock the file open and json load
    mock_json_load.return_value = {"data": [{"test": "payload"}]}
    mock_file = MagicMock()
    mock_path_open.return_value.__enter__.return_value = mock_file
    
    # Create args
    args = MagicMock()
    args.token = "test_token"
    args.files = ["test.json"]
    args.debug = False
    args.no_retry = False
    args.max_retries = 3
    
    # Also patch Path existence check to avoid FileNotFoundError
    with patch('pathlib.Path.exists', return_value=True):
        # Call function
        with patch.dict('os.environ', {}, clear=True):  # Ensure no env vars
            result = handle_send_command(args)
    
    # Verify
    assert result == 0
    assert mock_client.send_data.called
    assert mock_path_open.called
    assert mock_json_load.called


@patch('sendDetections.__main__.EnhancedApiClient')
def test_handle_send_command_no_token(mock_client_class):
    """Test handle_send_command with missing API token."""
    # Create args
    args = MagicMock()
    args.token = None
    args.files = ["test.json"]
    
    # Call function
    with patch.dict('os.environ', {}, clear=True):  # Ensure no env vars
        result = handle_send_command(args)
    
    # Verify
    assert result == 1  # Error code
    assert not mock_client_class.called


@pytest.mark.asyncio
@patch('sendDetections.__main__.BatchProcessor')
async def test_handle_batch_command(mock_processor_class):
    """Test handle_batch_command with successful processing."""
    # Setup mocks
    mock_processor = MagicMock()
    # Make process_files method an async mock that returns the expected value
    mock_processor.process_files = AsyncMock(return_value={
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    })
    mock_processor_class.return_value = mock_processor
    
    # Create args with minimal required attributes
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
    args.format = None  # Add format attribute for CLI compatibility
    
    # Patch Path existence check to ensure test.json "exists"
    with patch('pathlib.Path.exists', return_value=True):
        # Call function
        with patch.dict('os.environ', {}, clear=True):
            result = await handle_batch_command(args)
    
    # Verify
    assert result == 0
    mock_processor.process_files.assert_called_once()
    assert mock_processor.process_files.called