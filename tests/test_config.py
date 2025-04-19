"""
Unit tests for the config module.
Tests configuration settings, environment variable handling, and config file support.
"""

import os
import json
import tempfile
from pathlib import Path
import pytest

from sendDetections.config import (
    PROJECT_ROOT,
    API_URL,
    DEFAULT_HEADERS,
    SAMPLE_DIR,
    CSV_PATTERN,
    CSV_ENCODING,
    DEFAULT_API_OPTIONS,
    ConfigManager,
    get_config,
    get_api_url,
    get_api_options
)


class TestConfigSettings:
    """Tests for the config module settings."""
    
    def test_project_root(self):
        """Test PROJECT_ROOT is correctly configured."""
        assert isinstance(PROJECT_ROOT, Path)
        assert PROJECT_ROOT.exists()
        assert (PROJECT_ROOT / "sendDetections").exists()
        assert (PROJECT_ROOT / "sendDetections" / "__init__.py").exists()
    
    def test_api_url(self):
        """Test API_URL default and environment override."""
        default_url = "https://api.recordedfuture.com/collective-insights/detections"
        assert API_URL == default_url
        
        # Test with environment variable override
        test_url = "https://test-api.example.com/detections"
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("RF_API_URL", test_url)
            # Need to reimport to pickup new env var
            import importlib
            import sendDetections.config
            importlib.reload(sendDetections.config)
            assert sendDetections.config.API_URL == test_url
            
            # Restore default for other tests
            importlib.reload(sendDetections.config)
    
    def test_default_headers(self):
        """Test DEFAULT_HEADERS has correct content types."""
        assert "Accept" in DEFAULT_HEADERS
        assert DEFAULT_HEADERS["Accept"] == "application/json"
        assert "Content-Type" in DEFAULT_HEADERS
        assert DEFAULT_HEADERS["Content-Type"] == "application/json"
    
    def test_sample_dir(self):
        """Test SAMPLE_DIR points to valid directory."""
        assert isinstance(SAMPLE_DIR, Path)
        assert SAMPLE_DIR.exists()
        assert SAMPLE_DIR.is_dir()
        assert SAMPLE_DIR.name == "sample"
    
    def test_csv_pattern(self):
        """Test CSV_PATTERN for sample files."""
        assert CSV_PATTERN == "sample_*.csv"
        
        # Verify pattern matches actual files
        sample_files = list(SAMPLE_DIR.glob(CSV_PATTERN))
        assert len(sample_files) > 0
        for file_path in sample_files:
            assert file_path.name.startswith("sample_")
            assert file_path.suffix == ".csv"
    
    def test_csv_encoding(self):
        """Test CSV_ENCODING is set to UTF-8."""
        assert CSV_ENCODING == "utf-8"
    
    def test_default_api_options(self):
        """Test DEFAULT_API_OPTIONS has expected values."""
        assert isinstance(DEFAULT_API_OPTIONS, dict)
        assert "debug" in DEFAULT_API_OPTIONS
        assert DEFAULT_API_OPTIONS["debug"] is False
        assert "summary" in DEFAULT_API_OPTIONS
        assert DEFAULT_API_OPTIONS["summary"] is True
        
        # Test type annotations
        assert isinstance(DEFAULT_API_OPTIONS, dict)


class TestConfigManager:
    """Tests for the ConfigManager class."""
    
    def test_config_manager_initialization(self):
        """Test that ConfigManager initializes correctly."""
        config = ConfigManager()
        assert config.profile == "default"
        assert config.env_prefix == "RF_"
        assert config.config_file is None
        assert isinstance(config.config_data, dict)
    
    def test_config_manager_from_json_file(self):
        """Test loading configuration from a JSON file."""
        # Create a temporary JSON config file
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as temp_file:
            config_data = {
                "api_url": "https://test-api.example.com/detections",
                "max_concurrent": 10,
                "api_options_debug": True
            }
            temp_file.write(json.dumps(config_data))
            temp_file_path = temp_file.name
        
        try:
            # Test loading the config file
            config = ConfigManager(config_file=temp_file_path)
            
            # Verify values are loaded correctly
            assert config.get("api_url") == "https://test-api.example.com/detections"
            assert config.get("max_concurrent") == 10
            assert config.get("api_options_debug") is True
            
            # Verify default for non-existent keys
            assert config.get("non_existent_key", "default") == "default"
            
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    
    def test_config_manager_with_profiles(self):
        """Test configuration with profiles."""
        # Create a temporary JSON config file with profiles
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as temp_file:
            config_data = {
                "profiles": {
                    "default": {
                        "api_url": "https://default-api.example.com/detections",
                        "max_concurrent": 5
                    },
                    "dev": {
                        "api_url": "https://dev-api.example.com/detections",
                        "max_concurrent": 2,
                        "api_options_debug": True
                    }
                }
            }
            temp_file.write(json.dumps(config_data))
            temp_file_path = temp_file.name
        
        try:
            # Test loading the config file with default profile
            default_config = ConfigManager(config_file=temp_file_path)
            assert default_config.get("api_url") == "https://default-api.example.com/detections"
            assert default_config.get("max_concurrent") == 5
            
            # Test loading the config file with dev profile
            dev_config = ConfigManager(config_file=temp_file_path, profile="dev")
            assert dev_config.get("api_url") == "https://dev-api.example.com/detections"
            assert dev_config.get("max_concurrent") == 2
            assert dev_config.get("api_options_debug") is True
            
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    
    def test_environment_variable_priority(self):
        """Test that environment variables take precedence over config file values."""
        # Create a temporary JSON config file
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as temp_file:
            config_data = {
                "api_url": "https://config-file.example.com/detections",
                "max_concurrent": 7
            }
            temp_file.write(json.dumps(config_data))
            temp_file_path = temp_file.name
        
        try:
            # Set environment variables
            with pytest.MonkeyPatch().context() as mp:
                mp.setenv("RF_API_URL", "https://env-var.example.com/detections")
                
                # Load config with both env var and config file
                config = ConfigManager(config_file=temp_file_path)
                
                # Environment variable should take precedence
                assert config.get("api_url") == "https://env-var.example.com/detections"
                
                # Other values from config file should still be loaded
                assert config.get("max_concurrent") == 7
                
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    
    def test_type_conversion(self):
        """Test conversion of environment variable string values to appropriate types."""
        config = ConfigManager()
        
        # Test boolean conversion
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("RF_DEBUG", "true")
            mp.setenv("RF_VERBOSE", "false")
            mp.setenv("RF_ENABLED", "1")
            mp.setenv("RF_DISABLED", "0")
            
            assert config.get("debug") is True
            assert config.get("verbose") is False
            assert config.get("enabled") is True
            assert config.get("disabled") is False
        
        # Test number conversion
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("RF_INT_VALUE", "42")
            mp.setenv("RF_FLOAT_VALUE", "3.14")
            
            assert config.get("int_value") == 42
            assert config.get("float_value") == 3.14
            assert isinstance(config.get("int_value"), int)
            assert isinstance(config.get("float_value"), float)
    
    def test_get_dict_with_prefix(self):
        """Test getting all config values with a prefix."""
        # Create a temporary JSON config file
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as temp_file:
            config_data = {
                "api_options_debug": True,
                "api_options_summary": True,
                "api_options_timeout": 30,
                "other_value": "test"
            }
            temp_file.write(json.dumps(config_data))
            temp_file_path = temp_file.name
        
        try:
            # Load config
            config = ConfigManager(config_file=temp_file_path)
            
            # Get all api_options_ values
            api_options = config.get_dict("api_options_")
            
            # Verify correct values are returned
            assert len(api_options) == 3
            assert "api_options_debug" in api_options
            assert "api_options_summary" in api_options
            assert "api_options_timeout" in api_options
            assert api_options["api_options_debug"] is True
            assert api_options["api_options_timeout"] == 30
            
            # Verify other values are not included
            assert "other_value" not in api_options
            
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    
    def test_helper_functions(self):
        """Test helper functions for accessing configuration."""
        # Create a temporary JSON config file
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as temp_file:
            config_data = {
                "api_url": "https://helper-func.example.com/detections",
                "api_options_debug": True,
                "api_options_timeout": 60
            }
            temp_file.write(json.dumps(config_data))
            temp_file_path = temp_file.name
        
        try:
            # Create a new ConfigManager and replace the default one
            import sendDetections.config
            custom_config = ConfigManager(config_file=temp_file_path)
            original_config = sendDetections.config.config_manager
            sendDetections.config.config_manager = custom_config
            
            try:
                # Test get_config helper
                assert get_config("api_url") == "https://helper-func.example.com/detections"
                assert get_config("non_existent", "default") == "default"
                
                # Test get_api_url helper
                assert get_api_url() == "https://helper-func.example.com/detections"
                
                # Test get_api_options helper
                api_options = get_api_options()
                assert isinstance(api_options, dict)
                assert api_options["debug"] is True
                assert api_options["summary"] is True  # From DEFAULT_API_OPTIONS
                assert api_options["timeout"] == 60
                
            finally:
                # Restore the original config manager
                sendDetections.config.config_manager = original_config
                
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)