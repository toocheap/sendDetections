"""
Improved mocking tests for sendDetections using advanced mocking techniques.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import requests
from requests.exceptions import ConnectionError, Timeout

from sendDetections.api_client import DetectionApiClient, ApiError
from sendDetections.csv_converter import CSVConverter, CSVConversionError

class MockResponse:
    """Customizable mock response for flexible testing."""
    
    def __init__(self, status_code=200, json_data=None, raise_on_status=False, 
                 text="", error_on_json=False):
        self.status_code = status_code
        self._json_data = json_data or {}
        self._raise_on_status = raise_on_status
        self.text = text
        self.content = text.encode('utf-8') if text else b""
        self._error_on_json = error_on_json
        
    def raise_for_status(self):
        """Simulate HTTP errors when requested."""
        if self._raise_on_status:
            raise requests.exceptions.HTTPError(response=self)
            
    def json(self):
        """Return JSON data or raise ValueError for invalid JSON."""
        if self._error_on_json:
            raise ValueError("Invalid JSON")
        return self._json_data


# Simple CSV content for testing
VALID_CSV_CONTENT = """Entity ID,Entity,Detectors,Description,Malware,Mitre Codes,Event Source,Event ID,Detection Time
ip:1.1.1.1,1.1.1.1,detector_a,Test description 1,,,,evt-001,2025-04-18T01:00:00Z
domain:example.com,example.com,detector_b,Test description 2,,,,evt-002,2025-04-18T02:00:00Z
"""

# Advanced mock for testing retry logic and connection issues
class ConnectionMock:
    def __init__(self, max_failures=2, fail_type="connection"):
        self.attempts = 0
        self.max_failures = max_failures
        self.fail_type = fail_type
        
    def __call__(self, url, json, headers, **kwargs):
        self.attempts += 1
        
        # Simulate failures for the first few attempts
        if self.attempts <= self.max_failures:
            if self.fail_type == "connection":
                raise ConnectionError("Connection refused")
            elif self.fail_type == "timeout":
                raise Timeout("Request timed out")
            elif self.fail_type == "http":
                mock_resp = MockResponse(500, raise_on_status=True)
                return mock_resp
        
        # Succeed after max_failures attempts
        return MockResponse(200, json_data={
            "summary": {"submitted": 1, "processed": 1, "dropped": 0},
            "options": {"debug": False}
        })

# Test API client with various response scenarios
@pytest.mark.parametrize("mock_config,expected_outcome", [
    # Successful response
    (
        {"status_code": 200, "json_data": {"summary": {"submitted": 5}}},
        {"result": "success", "summary_submitted": 5}
    ),
    # JSON parsing error
    (
        {"status_code": 200, "error_on_json": True},
        {"result": "error", "error_type": ApiError, "message_contains": "Unexpected error"}
    ),
    # 401 Unauthorized
    (
        {"status_code": 401, "raise_on_status": True, "json_data": {"message": "Invalid token"}},
        {"result": "error", "error_type": ApiError, "message_contains": "Authentication failed"}
    ),
    # 503 Service Unavailable
    (
        {"status_code": 503, "raise_on_status": True},
        {"result": "error", "error_type": ApiError, "message_contains": "HTTP Error 503"}
    ),
])
def test_api_client_response_handling(monkeypatch, mock_config, expected_outcome):
    """Test API client handling of various response scenarios."""
    # Create mock response according to configuration
    mock_resp = MockResponse(**mock_config)
    
    def mock_post(url, json, headers, **kwargs):
        return mock_resp
        
    monkeypatch.setattr("requests.post", mock_post)
    
    # Test payload
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "detector_a", "name": "Test"}
            }
        ]
    }
    
    api_client = DetectionApiClient("test-token")
    
    if expected_outcome["result"] == "success":
        # Expect successful call
        response = api_client.send_data(payload)
        assert "summary" in response
        assert response["summary"]["submitted"] == expected_outcome["summary_submitted"]
    else:
        # Expect error
        with pytest.raises(expected_outcome["error_type"]) as excinfo:
            api_client.send_data(payload)
        assert expected_outcome["message_contains"] in str(excinfo.value)

# Test various combination of command-line options
@pytest.mark.parametrize("options,expected_output", [
    # Debug mode enabled
    (
        ["--debug"],
        {"options": {"debug": True}}
    ),
    # Custom options
    (
        [],
        {"options": {"debug": False, "summary": True}}
    ),
])
def test_api_client_options(monkeypatch, options, expected_output):
    """Test API client handling of various options."""
    # Create basic payload
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "detector_a"}
            }
        ]
    }
    
    # Configure return capture
    captured_json = None
    
    def mock_post(url, json, headers, **kwargs):
        nonlocal captured_json
        captured_json = json
        return MockResponse(200, {"success": True})
        
    monkeypatch.setattr("requests.post", mock_post)
    
    # Create API client with test options
    api_client = DetectionApiClient("test-token")
    debug = "--debug" in options
    
    # Call API
    api_client.send_data(payload, debug=debug)
    
    # Verify options in the sent JSON
    assert "options" in captured_json
    for key, value in expected_output["options"].items():
        assert captured_json["options"][key] == value

# Mock file system for CSV converter test
@pytest.fixture
def mock_csv_files(monkeypatch, tmp_path):
    """Create a mock CSV directory with sample files."""
    # Create sample files
    sample_dir = tmp_path / "sample"
    sample_dir.mkdir()
    
    files = {
        "sample_1.csv": """Entity ID,Entity,Detectors,Description,Malware,Mitre Codes,Event Source,Event ID,Detection Time
ip:1.1.1.1,1.1.1.1,detector_a,desc1,,,,evt-001,2025-04-18T01:00:00Z""",
        "sample_2.csv": """Entity ID,Entity,Detectors,Description,Malware,Mitre Codes,Event Source,Event ID,Detection Time
domain:example.com,example.com,detector_b,desc2,,,,evt-002,2025-04-18T02:00:00Z""",
        "other.csv": """Entity ID,Entity,Detectors,Description,Malware,Mitre Codes,Event Source,Event ID,Detection Time
ip:2.2.2.2,2.2.2.2,detector_c,desc3,,,,evt-003,2025-04-18T03:00:00Z"""
    }
    
    for name, content in files.items():
        (sample_dir / name).write_text(content)
    
    # Mock the SAMPLE_DIR in config
    monkeypatch.setattr("sendDetections.config.SAMPLE_DIR", sample_dir)
    
    return sample_dir

def test_csv_converter_batch_run(mock_csv_files):
    """Test batch conversion of CSV files."""
    # Override the default pattern to match our test files
    converter = CSVConverter(csv_pattern="sample_*.csv", input_dir=mock_csv_files)
    json_files = converter.run()
    
    # Should find 2 matching files (sample_1.csv and sample_2.csv)
    assert len(json_files) == 2
    
    # Check that output JSON files exist
    assert all(f.exists() for f in json_files)
    assert all(f.suffix == '.json' for f in json_files)
    
    # Check content of first output file
    with json_files[0].open('r') as f:
        data = json.load(f)
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 1

def test_csv_converter_custom_pattern(mock_csv_files):
    """Test CSV converter with custom pattern."""
    # Use custom pattern to match all CSV files
    converter = CSVConverter(csv_pattern="*.csv", input_dir=mock_csv_files)
    json_files = converter.run()
    
    # Should find 3 matching files
    assert len(json_files) == 3