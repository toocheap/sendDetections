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
        args = parser.parse_args(["--config", "test_config.yml", "convert"])
        
        assert args.config == "test_config.yml"
        assert args.command == "convert"
    
    def test_profile_argument(self):
        """Test that the --profile argument is properly defined."""
        parser = setup_argparse()
        args = parser.parse_args(["--profile", "dev", "convert"])
        
        assert args.profile == "dev"
        assert args.command == "convert"
    
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
            mock_args.command = None  # This will cause an early return
            mock_args.log_level = "info"
            mock_args.json_logs = False
            mock_args.log_file = None
            mock_parse_args.return_value = mock_args
            
            # Call main
            main()
            
            # Verify ConfigManager was called with correct arguments
            mock_config_manager.assert_called_with(
                config_file="test_config.yml",
                profile="dev"
            )
    
    @pytest.mark.asyncio
    async def test_config_values_used_in_batch_command(self):
        """Test that configuration values are used in the batch command."""
        # Create a modified handle_batch_command for testing
        from sendDetections.__main__ import handle_batch_command
        
        # Test with mocked config values
        with patch("sendDetections.config.get_config") as mock_get_config:
            # Set up return values for the mock
            mock_get_config.side_effect = lambda key, default=None: {
                "api_url": "https://test-api.example.com/detections",
                "max_concurrent": 10,
                "batch_size": 200,
                "max_retries": 5,
                "api_token": "test-token-123"
            }.get(key, default)
            
            # Test with the CLI's handle_batch_command
            with patch("sendDetections.__main__.BatchProcessor") as mock_batch_processor:
                # Mock os.getenv for RF_API_TOKEN
                with patch("os.getenv", return_value=None):
                    # Mock args
                    args = MagicMock()
                    args.token = None
                    args.max_concurrent = None  # None should make it use the config value
                    args.batch_size = None      # None should make it use the config value
                    args.max_retries = None     # None should make it use the config value
                    args.no_progress = False
                    args.files = []  # To prevent further execution
                    
                    # Prepare mock batch processor
                    mock_instance = MagicMock()
                    mock_batch_processor.return_value = mock_instance
                    
                    # Handle_batch_command will exit early when it sees args.files is empty
                    await handle_batch_command(args)
                    
                    # Check that BatchProcessor was initialized with config values
                    mock_batch_processor.assert_called_once()
                    _, kwargs = mock_batch_processor.call_args
                    
                    # Verify the config values were used
                    assert kwargs.get("api_token") == "test-token-123"
                    assert kwargs.get("max_concurrent") == 10
                    assert kwargs.get("batch_size") == 200
                    assert kwargs.get("max_retries") == 5