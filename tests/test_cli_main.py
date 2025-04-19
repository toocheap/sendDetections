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
    main, setup_argparse, handle_submit_command
)


class TestCliSetup:
    """Tests for CLI setup and argument parsing."""
    
    def test_setup_argparse(self):
        """Test argument parser setup."""
        parser = setup_argparse()
        
        # Test parsing file arguments
        args = parser.parse_args(['dummy.csv'])
        assert args.files == ['dummy.csv']
    
    def test_file_arguments(self):
        """Test file arguments."""
        parser = setup_argparse()
        args = parser.parse_args(['file1.csv', 'file2.json'])
        
        assert args.files == ['file1.csv', 'file2.json']
        assert args.input_dir is None
        assert args.token is None
        assert args.debug is False
    
    def test_token_argument(self):
        """Test token argument."""
        parser = setup_argparse()
        args = parser.parse_args(['--token', 'api_token', 'file.csv'])
        
        assert args.token == 'api_token'
        assert args.files == ['file.csv']


@patch('sys.stderr')  # Silence the error messages during test
def test_main_with_files(mock_stderr):
    """Test main function with file parameters."""
    with patch('sys.argv', ['sendDetections', 'file1.csv']):
        with patch('sendDetections.__main__.configure_logging'):
            # Must return completed coroutine
            mock_async_result = MagicMock(return_value=0)
            with patch('asyncio.run', mock_async_result):
                mock_args = MagicMock()
                mock_args.files = ['file1.csv']
                mock_args.config = None
                mock_args.profile = "default"
                mock_args.log_level = "info"
                mock_args.json_logs = False
                mock_args.log_file = None
                with patch('sendDetections.__main__.setup_argparse') as mock_parser:
                    mock_parser.return_value.parse_args.return_value = mock_args
                    exit_code = main()
                    assert exit_code == 0
                    assert mock_async_result.called


@patch('sys.stderr')  # Silence the error messages during test
def test_main_with_options(mock_stderr):
    """Test main function with options."""
    with patch('sys.argv', ['sendDetections', '--debug', 'file1.csv']):
        with patch('sendDetections.__main__.configure_logging'):
            # Must return completed coroutine
            mock_async_result = MagicMock(return_value=0)
            with patch('asyncio.run', mock_async_result):
                mock_args = MagicMock()
                mock_args.files = ['file1.csv']
                mock_args.debug = True
                mock_args.config = None
                mock_args.profile = "default"
                mock_args.log_level = "info"
                mock_args.json_logs = False
                mock_args.log_file = None
                with patch('sendDetections.__main__.setup_argparse') as mock_parser:
                    mock_parser.return_value.parse_args.return_value = mock_args
                    exit_code = main()
                    assert exit_code == 0
                    assert mock_async_result.called


# これらのテストは新しいコマンドライン構造では不要となりました
# 代わりに test_main_with_files および test_main_with_options を使用します


def test_keyboard_interrupt_handling():
    """Test that keyboard interrupts are handled gracefully."""
    with patch('sys.argv', ['sendDetections', 'file.csv']):
        with patch('sendDetections.__main__.configure_logging'):
            # Setup args
            mock_args = MagicMock()
            mock_args.files = ['file.csv']
            mock_args.config = None
            mock_args.profile = "default"
            mock_args.log_level = "info"
            mock_args.json_logs = False
            mock_args.log_file = None
            
            with patch('sendDetections.__main__.setup_argparse') as mock_parser:
                mock_parser.return_value.parse_args.return_value = mock_args
                # Simulate KeyboardInterrupt
                with patch('asyncio.run', side_effect=KeyboardInterrupt):
                    exit_code = main()
                    assert exit_code == 130  # SIGINT code


@patch('sendDetections.__main__.configure_logging')
def test_unexpected_exception_handling(mock_configure_logging):
    """Test that unexpected exceptions are caught and handled."""
    mock_args = MagicMock()
    mock_args.files = ['file.csv']
    mock_args.config = None
    mock_args.profile = "default"
    mock_args.log_level = "info"
    mock_args.json_logs = False
    mock_args.log_file = None
    
    with patch('sys.argv', ['sendDetections', 'file.csv']):
        with patch('sendDetections.__main__.setup_argparse') as mock_parser:
            mock_parser.return_value.parse_args.return_value = mock_args
            # Simulate unexpected exception
            with patch('asyncio.run', side_effect=Exception("Unexpected error")):
                exit_code = main()
                assert exit_code == 1  # Error code