#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the organizations command functionality of sendDetections.
"""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

from sendDetections.__main__ import (
    main, setup_argparse, handle_organizations_command
)


class TestOrganizationsCommand:
    """Tests for organizations command arguments and processing."""
    
    def test_organizations_command_arguments(self):
        """Test organizations command arguments."""
        parser = setup_argparse()
        args = parser.parse_args([
            'organizations',
            '--token', 'api_token'
        ])
        
        assert args.command == 'organizations'
        assert args.token == 'api_token'


@patch('sendDetections.__main__.configure_logging')
@patch('sendDetections.__main__.handle_organizations_command')
def test_main_organizations_command(mock_handle_organizations, mock_configure_logging):
    """Test main function with organizations command."""
    mock_handle_organizations.return_value = 0
    
    with patch('sys.argv', ['sendDetections', 'organizations']):
        exit_code = main()
        
    assert exit_code == 0
    assert mock_handle_organizations.called


def test_handle_organizations_command_success():
    """Test handle_organizations_command with successful execution."""
    # Create args
    args = MagicMock()
    args.token = "test_token"
    
    # Mock builtins.print to capture output
    with patch('builtins.print') as mock_print:
        # Call function
        with patch.dict('os.environ', {"RF_API_TOKEN": "test_token"}, clear=True):
            result = handle_organizations_command(args)
    
    # Verify
    assert result == 0
    mock_print.assert_called()  # Ensure something was printed


def test_handle_organizations_command_no_token():
    """Test handle_organizations_command with missing API token."""
    # Create args
    args = MagicMock()
    args.token = None
    
    # Call function
    with patch.dict('os.environ', {}, clear=True):  # Ensure no env vars
        result = handle_organizations_command(args)
    
    # Verify
    assert result == 1  # Error code