"""
Unit tests for the config module.
Tests configuration settings and environment variable handling.
"""

import os
from pathlib import Path
import pytest

from sendDetections.config import (
    PROJECT_ROOT,
    API_URL,
    DEFAULT_HEADERS,
    SAMPLE_DIR,
    CSV_PATTERN,
    CSV_ENCODING,
    DEFAULT_API_OPTIONS
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