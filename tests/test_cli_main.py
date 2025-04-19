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
    main, setup_argparse, handle_submit_command,
    handle_organizations_command
)


class TestCliSetup:
    """Tests for CLI setup and argument parsing."""
    
    def test_setup_argparse(self):
        """Test argument parser setup."""
        parser = setup_argparse()
        
        # Test that the parser has the expected commands
        args = parser.parse_args(['submit', 'dummy.csv'])
        assert args.command == 'submit'
        
        args = parser.parse_args(['organizations', '--token', 'dummy_token'])
        assert args.command == 'organizations'
    
    def test_submit_command_arguments(self):
        """Test submit command arguments."""
        parser = setup_argparse()
        args = parser.parse_args(['submit', 'file1.csv', 'file2.json'])
        
        assert args.command == 'submit'
        assert args.files == ['file1.csv', 'file2.json']
        assert args.input_dir is None
        assert args.token is None
        assert args.debug is False
    
    def test_organizations_command_arguments(self):
        """Test organizations command arguments."""
        parser = setup_argparse()
        args = parser.parse_args(['organizations', '--token', 'api_token'])
        
        assert args.command == 'organizations'
        assert args.token == 'api_token'


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
@patch('sendDetections.__main__.handle_submit_command')
@patch('asyncio.run')
def test_main_submit_command(mock_asyncio_run, mock_handle_submit, mock_configure_logging):
    """Test main function with submit command."""
    mock_asyncio_run.return_value = 0
    
    with patch('sys.argv', ['sendDetections', 'submit', 'file.csv']):
        exit_code = main()
        
    assert exit_code == 0
    assert mock_asyncio_run.called
    mock_handle_submit.assert_called_once()


@patch('sendDetections.__main__.configure_logging')
@patch('sendDetections.__main__.handle_organizations_command')
def test_main_organizations_command(mock_handle_organizations, mock_configure_logging):
    """Test main function with organizations command."""
    mock_handle_organizations.return_value = 0
    
    with patch('sys.argv', ['sendDetections', 'organizations']):
        exit_code = main()
        
    assert exit_code == 0
    assert mock_handle_organizations.called


def test_keyboard_interrupt_handling():
    """Test that keyboard interrupts are handled gracefully."""
    with patch('sys.argv', ['sendDetections', 'submit']):
        with patch('sendDetections.__main__.configure_logging'):
            with patch('asyncio.run', side_effect=KeyboardInterrupt):
                exit_code = main()
                assert exit_code == 130  # SIGINT code


@patch('sendDetections.__main__.configure_logging')
def test_unexpected_exception_handling(mock_configure_logging):
    """Test that unexpected exceptions are caught and handled."""
    with patch('sys.argv', ['sendDetections', 'submit']):
        with patch('asyncio.run', side_effect=Exception("Unexpected error")):
            exit_code = main()
            assert exit_code == 1  # Error code