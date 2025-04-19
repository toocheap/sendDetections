#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Additional tests for the main CLI functionality of sendDetections.
Focus on configuration and profile handling.
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
    main, setup_argparse
)
from sendDetections.errors import (
    ApiError, ApiAuthenticationError, ApiRateLimitError,
    ApiConnectionError, CSVConversionError
)


class TestConfigurationOptions:
    """Tests for CLI configuration options."""
    
    def test_config_file_option(self):
        """Test configuration file option."""
        parser = setup_argparse()
        args = parser.parse_args([
            '--config', 'my_config.yml',
            'file.csv'
        ])
        
        assert args.config == 'my_config.yml'
        assert args.files == ['file.csv']
        
    def test_profile_option(self):
        """Test profile option."""
        parser = setup_argparse()
        args = parser.parse_args([
            '--profile', 'dev',
            'file.csv'
        ])
        
        assert args.profile == 'dev'
        assert args.files == ['file.csv']
        
    def test_submit_with_configfile_and_profile(self):
        """Test submit command with config file and profile options."""
        parser = setup_argparse()
        args = parser.parse_args([
            '--config', 'my_config.yml',
            '--profile', 'dev',
            'file.csv',
            '--token', 'override_token'
        ])
        
        assert args.config == 'my_config.yml'
        assert args.profile == 'dev'
        assert args.token == 'override_token'
        assert args.files == ['file.csv']


class TestLoggingOptions:
    """Tests for logging configuration options."""
    
    def test_log_level_option(self):
        """Test log level option."""
        parser = setup_argparse()
        args = parser.parse_args([
            '--log-level', 'debug',
            'file.csv'
        ])
        
        assert args.log_level == 'debug'
        assert args.files == ['file.csv']
        
    def test_json_logs_option(self):
        """Test JSON logs option."""
        parser = setup_argparse()
        args = parser.parse_args([
            '--json-logs',
            'file.csv'
        ])
        
        assert args.json_logs is True
        assert args.files == ['file.csv']
        
    def test_log_file_option(self):
        """Test log file option."""
        parser = setup_argparse()
        args = parser.parse_args([
            '--log-file', 'debug.log',
            'file.csv'
        ])
        
        assert args.log_file == 'debug.log'
        assert args.files == ['file.csv']


@patch('sendDetections.__main__.configure_logging')
@patch('sendDetections.config.ConfigManager')
def test_main_with_config_file(mock_config_manager, mock_configure_logging):
    """Test main function with config file option."""
    mock_config = MagicMock()
    mock_config_manager.return_value = mock_config
    
    with patch('sys.argv', ['sendDetections', '--config', 'my_config.yml', 'file.csv']):
        # Setup mock args
        mock_args = MagicMock()
        mock_args.config = 'my_config.yml'
        mock_args.profile = 'default'
        mock_args.files = ['file.csv']
        mock_args.log_level = 'info'
        mock_args.json_logs = False
        mock_args.log_file = None
        
        with patch('sendDetections.__main__.setup_argparse') as mock_parser:
            mock_parser.return_value.parse_args.return_value = mock_args
            # Use regular mock instead of AsyncMock to avoid coroutine issues
            mock_async_result = MagicMock(return_value=0)
            with patch('asyncio.run', mock_async_result):
                exit_code = main()
    
    assert exit_code == 0
    mock_config_manager.assert_called_with(config_file='my_config.yml', profile='default')


@patch('sendDetections.__main__.configure_logging')
@patch('sendDetections.config.ConfigManager')
def test_main_with_profile(mock_config_manager, mock_configure_logging):
    """Test main function with profile option."""
    mock_config = MagicMock()
    mock_config_manager.return_value = mock_config
    
    with patch('sys.argv', ['sendDetections', '--profile', 'dev', 'file.csv']):
        # Setup mock args
        mock_args = MagicMock()
        mock_args.config = None
        mock_args.profile = 'dev'
        mock_args.files = ['file.csv']
        mock_args.log_level = 'info'
        mock_args.json_logs = False
        mock_args.log_file = None
        
        with patch('sendDetections.__main__.setup_argparse') as mock_parser:
            mock_parser.return_value.parse_args.return_value = mock_args
            # Use regular mock instead of AsyncMock to avoid coroutine issues
            mock_async_result = MagicMock(return_value=0)
            with patch('asyncio.run', mock_async_result):
                exit_code = main()
    
    assert exit_code == 0
    mock_config_manager.assert_called_with(config_file=None, profile='dev')