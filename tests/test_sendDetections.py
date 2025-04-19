import json
import tempfile
from pathlib import Path
import pytest
import requests
from sendDetections.api_client import DetectionApiClient, ApiError
from sendDetections.csv_converter import CSVConverter, CSVConversionError
from sendDetections.validators import validate_payload

SAMPLE_CSV = """Entity ID,Entity,Detectors,Description,Malware,Mitre Codes,Event Source,Event ID,Detection Time
ip:1.2.3.4,1.2.3.4,detector_a,Test detection,malware1,MITRE-123,source_a,evt-001,2025-04-18T00:00:00Z
"""

def csv_to_payload(csv_path: Path) -> dict:
    """Helper for test: convert CSV to payload dict using CSVConverter."""
    converter = CSVConverter()
    try:
        payload = converter.csv_to_payload(csv_path)
        return payload
    except CSVConversionError as e:
        pytest.fail(f"CSV conversion failed: {str(e)}")
        return {}

def test_csv_to_payload_conversion():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "sample.csv"
        csv_path.write_text(SAMPLE_CSV, encoding="utf-8")
        payload = csv_to_payload(csv_path)
        assert "data" in payload
        assert isinstance(payload["data"], list)
        assert payload["data"][0]["ioc"]["type"] == "ip"
        assert payload["data"][0]["ioc"]["value"] == "1.2.3.4"
        assert payload["data"][0]["detection"]["type"] == "detector_a"
        assert payload["data"][0]["detection"]["name"] == "Test detection"
        assert payload["data"][0]["timestamp"] == "2025-04-18T00:00:00Z"

def test_payload_validation():
    # Test validation
    # No data field
    assert "Validation error at 'data'" in validate_payload({})
    
    # Empty data array
    assert "Validation error at 'data'" in validate_payload({"data": []})
    
    # Missing IoC type
    payload = {
        "data": [
            {
                "ioc": {"value": "1.2.3.4"},
                "detection": {"type": "detector_a"}
            }
        ]
    }
    assert "Validation error at 'data.0.ioc.type'" in validate_payload(payload)
    
    # Missing detection.sub_type for detection_rule
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "detection_rule"}
            }
        ]
    }
    assert "sub_type" in validate_payload(payload)

def test_send_data_success(monkeypatch):
    """
    Test DetectionApiClient.send_data with a mocked successful API response.
    """
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "detector_a", "name": "desc"},
                "timestamp": "2025-04-18T00:00:00Z"
            }
        ]
    }
    api_token = "dummy-token"
    class MockResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "summary": {"submitted": 1, "processed": 1, "dropped": 0, "transient_ids": []},
                "options": {"debug": False}
            }
    def mock_post(url, json, headers, **kwargs):
        assert url.startswith("https://api.recordedfuture.com/")
        assert headers["X-RFToken"] == api_token
        return MockResponse()
    monkeypatch.setattr("requests.post", mock_post)
    
    api_client = DetectionApiClient(api_token)
    resp = api_client.send_data(payload)
    assert resp["summary"]["submitted"] == 1
    assert resp["options"]["debug"] is False

def test_send_data_http_error(monkeypatch):
    """
    Test DetectionApiClient.send_data error handling (HTTP 400).
    """
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "detector_a", "name": "desc"},
                "timestamp": "2025-04-18T00:00:00Z"
            }
        ]
    }
    api_token = "dummy-token"
    
    class MockResponse:
        status_code = 400
        def raise_for_status(self):
            raise requests.exceptions.HTTPError(response=self)
        def json(self):
            return {"message": "Bad Request"}
    def mock_post(url, json, headers, **kwargs):
        return MockResponse()
    monkeypatch.setattr("requests.post", mock_post)
    
    api_client = DetectionApiClient(api_token)
    with pytest.raises(ApiError) as excinfo:
        api_client.send_data(payload)
    
    assert "Bad Request" in str(excinfo.value)
