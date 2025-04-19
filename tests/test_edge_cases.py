"""
Edge case tests for sendDetections using parameterized tests.
"""

import json
import tempfile
from pathlib import Path

import pytest
import requests
from pydantic import ValidationError

from sendDetections.api_client import DetectionApiClient, ApiError
from sendDetections.csv_converter import CSVConverter, CSVConversionError
from sendDetections.validators import validate_payload

# Parameterized tests for edge cases in payload validation
@pytest.mark.parametrize("payload,expected_error_fragment", [
    # Empty payloads
    ({}, "data"),
    ({"data": []}, "data"),
    
    # Invalid IoC types
    (
        {"data": [{"ioc": {"type": "invalid_type", "value": "1.2.3.4"}, "detection": {"type": "detector_a"}}]},
        "IoC type must be one of"
    ),
    
    # Empty values
    (
        {"data": [{"ioc": {"type": "ip", "value": ""}, "detection": {"type": "detector_a"}}]},
        "IoC value cannot be empty"
    ),
    
    # Invalid timestamp format
    (
        {"data": [{"ioc": {"type": "ip", "value": "1.2.3.4"}, "detection": {"type": "detector_a"}, "timestamp": "2023/01/01"}]},
        "Timestamp must be in ISO 8601 format"
    ),
    
    # Missing sub_type for detection_rule
    (
        {"data": [{"ioc": {"type": "ip", "value": "1.2.3.4"}, "detection": {"type": "detection_rule"}}]},
        "sub_type"
    ),
    
    # Invalid detection type
    (
        {"data": [{"ioc": {"type": "ip", "value": "1.2.3.4"}, "detection": {"type": "invalid_detector"}}]},
        "Detection type must be one of"
    ),
])
def test_payload_validation_edge_cases(payload, expected_error_fragment):
    """Test validation of edge cases."""
    error = validate_payload(payload)
    assert error is not None, f"Expected validation error for payload: {payload}"
    assert expected_error_fragment in error, f"Expected error fragment '{expected_error_fragment}' not found in error: {error}"

# Test CSV conversion edge cases
@pytest.mark.parametrize("csv_content,expected_error_fragment", [
    # Missing required columns
    (
        "Entity,Detectors,Description\nip1,detector1,desc1",
        "IoC type"
    ),
    
    # Invalid or empty entity ID
    (
        "Entity ID,Entity,Detectors,Description\n,1.1.1.1,detector_a,desc",
        "IoC type"
    ),
    
    # Missing detector
    (
        "Entity ID,Entity,Detectors,Description\nip:1.1.1.1,1.1.1.1,,desc",
        "Detection type"
    ),
])
def test_csv_conversion_edge_cases(csv_content, expected_error_fragment):
    """Test CSV conversion for edge cases."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "invalid.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        
        converter = CSVConverter()
        with pytest.raises(CSVConversionError) as excinfo:
            converter.csv_to_payload(csv_path)
            
        assert expected_error_fragment in str(excinfo.value)

# Test API client error handling for different scenarios
@pytest.mark.parametrize("status_code,error_msg,expected_fragment", [
    (400, "Invalid payload format", "Bad Request"),
    (401, "Invalid API token", "Authentication failed"),
    (403, "Forbidden access", "Access denied"),
    (429, "Rate limit exceeded", "Too many requests"),
    (500, "Internal server error", "Server internal error"),
])
def test_api_client_error_handling(monkeypatch, status_code, error_msg, expected_fragment):
    """Test API client error handling for various HTTP error codes."""
    class MockErrorResponse:
        def __init__(self, status, message):
            self.status_code = status
            self.message = message
            
        def raise_for_status(self):
            raise requests.exceptions.HTTPError(response=self)
            
        def json(self):
            return {"message": self.message}
    
    # Mock requests.post to return an error response
    def mock_post(url, json, headers, **kwargs):
        return MockErrorResponse(status_code, error_msg)
    
    monkeypatch.setattr("requests.post", mock_post)
    
    valid_payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "correlation", "name": "test"},
            }
        ]
    }
    
    api_client = DetectionApiClient("dummy-token")
    
    with pytest.raises(ApiError) as excinfo:
        api_client.send_data(valid_payload)
    
    # Verify that the correct error message is returned
    error_message = str(excinfo.value)
    assert expected_fragment in error_message
    assert error_msg in error_message
    assert excinfo.value.status_code == status_code

# Test CSV converter with different IoC types
@pytest.mark.parametrize("entity_id,expected_type,expected_value", [
    ("ip:192.168.1.1", "ip", "192.168.1.1"),
    ("domain:example.com", "domain", "example.com"),
    ("hash:a1b2c3d4e5f6", "hash", "a1b2c3d4e5f6"),
    ("url:https://example.com/path", "url", "https://example.com/path"),
    ("vulnerability:CVE-2023-12345", "vulnerability", "CVE-2023-12345"),
])
def test_csv_converter_ioc_types(entity_id, expected_type, expected_value):
    """Test CSV converter with different IoC types."""
    csv_content = f"""Entity ID,Entity,Detectors,Description
{entity_id},{expected_value},detector_a,Test description
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "test.csv"
        csv_path.write_text(csv_content, encoding="utf-8")
        
        converter = CSVConverter()
        payload = converter.csv_to_payload(csv_path)
        
        assert len(payload["data"]) == 1
        assert payload["data"][0]["ioc"]["type"] == expected_type
        assert payload["data"][0]["ioc"]["value"] == expected_value