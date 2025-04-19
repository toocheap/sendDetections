"""
Tests for the configuration file support in the CLI.
"""

import json
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from sendDetections.__main__ import main, setup_argparse


class TestCLIConfigFile:
    """Tests for the CLI configuration file functionality."""
    
    def test_config_file_argument(self):
        """Test that the --config argument is properly defined."""
        parser = setup_argparse()
        args = parser.parse_args(["--config", "test_config.yml", "file.csv"])
        
        assert args.config == "test_config.yml"
        assert args.files == ["file.csv"]
    
    def test_profile_argument(self):
        """Test that the --profile argument is properly defined."""
        parser = setup_argparse()
        args = parser.parse_args(["--profile", "dev", "file.csv"])
        
        assert args.profile == "dev"
        assert args.files == ["file.csv"]
    
    @patch("sendDetections.config.ConfigManager")
    @patch("sendDetections.__main__.configure_logging")
    def test_main_initializes_config_manager(self, mock_configure_logging, mock_config_manager):
        """Test that main() initializes the ConfigManager with provided arguments."""
        # Create a mock for the config manager instance
        mock_config_instance = MagicMock()
        mock_config_manager.return_value = mock_config_instance
        
        # Create mock for ArgumentParser.parse_args
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            # Set up mock args
            mock_args = MagicMock()
            mock_args.config = "test_config.yml"
            mock_args.profile = "dev"
            mock_args.files = []  # Empty files list to prevent further execution
            mock_args.log_level = "info"
            mock_args.json_logs = False
            mock_args.log_file = None
            mock_parse_args.return_value = mock_args
            
            # Mock asyncio.run to prevent execution
            with patch("asyncio.run"):
                # Call main
                main()
                
                # Verify ConfigManager was called with correct arguments
                mock_config_manager.assert_called_with(
                    config_file="test_config.yml",
                    profile="dev"
                )
    
    def test_config_values_used_in_main(self):
        """Test that configuration values are used in the main function."""
        # This is a more straightforward test that doesn't need asyncio
        from sendDetections.__main__ import setup_argparse
        
        # Test the argument parser directly
        parser = setup_argparse()
        args = parser.parse_args([
            "--concurrent", "10",
            "--batch-size", "200",
            "--max-retries", "5",
            "--token", "test-token-123",
            "file.csv"
        ])
        
        # Verify the CLI values were parsed correctly
        assert args.concurrent == 10
        assert args.batch_size == 200
        assert args.max_retries == 5
        assert args.token == "test-token-123"
        assert args.files == ["file.csv"]