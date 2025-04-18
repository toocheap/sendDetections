import json
import tempfile
from pathlib import Path
import pytest
from sendDetections.api_client import DetectionApiClient
from sendDetections.csv_converter import CSVConverter

SAMPLE_CSV = """Entity ID,Entity,Detectors,Description,Malware,Mitre Codes,Event Source,Event ID,Detection Time
ip:1.2.3.4,1.2.3.4,detector_a,Test detection,malware1,MITRE-123,source_a,evt-001,2025-04-18T00:00:00Z
"""

def csv_to_payload(csv_path: Path) -> dict:
    """Helper for test: convert CSV to payload dict using CSVConverter."""
    converter = CSVConverter()
    with csv_path.open(encoding="utf-8") as f:
        import csv as _csv
        reader = _csv.DictReader(f)
        data = [converter.csv_row_to_dataentry(row) for row in reader]
    payload = {"data": data}
    err = converter.validate_payload(payload)
    assert err is None, f"Payload validation failed: {err}"
    return payload

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
    # ...（省略：既存のテスト内容はそのまま）...
    # No data field
    assert "'data' is missing" in DetectionApiClient.validate_payload({})

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
    resp = DetectionApiClient.send_data(payload, api_token)
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
    class MockHTTPError(Exception):
        def __init__(self, response):
            self.response = response
    class MockResponse:
        status_code = 400
        def raise_for_status(self):
            raise requests.exceptions.HTTPError(response=self)
        def json(self):
            return {"message": "Bad Request"}
    def mock_post(url, json, headers, **kwargs):
        return MockResponse()
    monkeypatch.setattr("requests.post", mock_post)
    import sys
    import pytest
    with pytest.raises(SystemExit):
        DetectionApiClient.send_data(payload, api_token)
