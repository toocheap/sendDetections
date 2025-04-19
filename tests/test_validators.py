"""
Unit tests for the validators module.
Tests schema validation for Recorded Future API payloads.
"""

import json
from typing import Any, Dict, Optional
import pytest
from pydantic import ValidationError

from sendDetections.validators import (
    validate_payload,
    ApiPayload,
    DataEntry,
    IoC,
    Detection,
    Incident,
    ApiOptions
)


class TestIoCModel:
    """Tests for the IoC validation model."""

    def test_valid_ioc(self):
        """Test valid IoC objects."""
        valid_iocs = [
            {"type": "ip", "value": "192.168.1.1"},
            {"type": "domain", "value": "example.com", "source_type": "firewall"},
            {"type": "hash", "value": "a1b2c3d4e5f6", "field": "file_hash"},
            {"type": "vulnerability", "value": "CVE-2023-12345"},
            {"type": "url", "value": "https://example.com/path"},
        ]
        
        for ioc_data in valid_iocs:
            ioc = IoC(**ioc_data)
            assert ioc.type == ioc_data["type"]
            assert ioc.value == ioc_data["value"]
    
    def test_invalid_ioc_type(self):
        """Test IoC with invalid type."""
        with pytest.raises(ValidationError) as excinfo:
            IoC(type="invalid_type", value="test")
        
        error_msg = str(excinfo.value)
        assert "IoC type must be one of" in error_msg
    
    def test_empty_ioc_value(self):
        """Test IoC with empty value."""
        with pytest.raises(ValidationError) as excinfo:
            IoC(type="ip", value="")
        
        error_msg = str(excinfo.value)
        assert "IoC value cannot be empty" in error_msg


class TestDetectionModel:
    """Tests for the Detection validation model."""
    
    def test_valid_detection(self):
        """Test valid Detection objects."""
        valid_detections = [
            {"type": "correlation", "id": "p_123"},
            {"type": "playbook", "name": "Test Playbook"},
            {"type": "detection_rule", "sub_type": "sigma", "id": "doc:123"},
            {"type": "sandbox", "name": "Sandbox Detection"},
            {"type": "detector_custom", "name": "Custom Detector"}
        ]
        
        for detection_data in valid_detections:
            detection = Detection(**detection_data)
            assert detection.type == detection_data["type"]
    
    def test_invalid_detection_type(self):
        """Test Detection with invalid type."""
        with pytest.raises(ValidationError) as excinfo:
            Detection(type="invalid_type")
        
        error_msg = str(excinfo.value)
        assert "Detection type must be one of" in error_msg
    
    def test_detection_rule_without_subtype(self):
        """Test detection_rule type without required sub_type."""
        with pytest.raises(ValidationError) as excinfo:
            Detection(type="detection_rule")
        
        error_msg = str(excinfo.value)
        assert "sub_type" in error_msg


class TestDataEntryModel:
    """Tests for the DataEntry validation model."""
    
    def test_valid_data_entry(self):
        """Test valid DataEntry objects."""
        valid_entry = {
            "ioc": {"type": "ip", "value": "1.2.3.4"},
            "detection": {"type": "correlation", "id": "p_123"},
            "timestamp": "2023-01-01T10:00:00Z",
            "mitre_codes": ["T1055"],
            "malwares": ["TestMalware"]
        }
        
        entry = DataEntry(**valid_entry)
        assert entry.ioc.type == "ip"
        assert entry.ioc.value == "1.2.3.4"
        assert entry.detection.type == "correlation"
        assert entry.timestamp == "2023-01-01T10:00:00Z"
    
    def test_data_entry_with_incident(self):
        """Test DataEntry with Incident information."""
        entry_data = {
            "ioc": {"type": "ip", "value": "1.2.3.4"},
            "detection": {"type": "correlation"},
            "incident": {
                "id": "incident-123",
                "name": "Test Incident",
                "type": "security-event"
            }
        }
        
        entry = DataEntry(**entry_data)
        assert entry.incident is not None
        assert entry.incident.id == "incident-123"
        assert entry.incident.name == "Test Incident"
    
    def test_invalid_timestamp(self):
        """Test DataEntry with invalid timestamp format."""
        entry_data = {
            "ioc": {"type": "ip", "value": "1.2.3.4"},
            "detection": {"type": "correlation"},
            "timestamp": "2023/01/01"  # Invalid format
        }
        
        with pytest.raises(ValidationError) as excinfo:
            DataEntry(**entry_data)
        
        error_msg = str(excinfo.value)
        assert "Timestamp must be in ISO 8601 format" in error_msg


class TestApiPayloadModel:
    """Tests for the ApiPayload validation model."""
    
    def test_valid_payload(self):
        """Test valid ApiPayload."""
        payload_data = {
            "data": [
                {
                    "ioc": {"type": "ip", "value": "1.2.3.4"},
                    "detection": {"type": "correlation"}
                }
            ],
            "options": {"debug": True, "summary": False},
            "organization_ids": ["org1", "org2"]
        }
        
        payload = ApiPayload(**payload_data)
        assert len(payload.data) == 1
        assert payload.options is not None
        assert payload.options.debug is True
        assert payload.options.summary is False
        assert payload.organization_ids == ["org1", "org2"]
    
    def test_empty_data_array(self):
        """Test ApiPayload with empty data array."""
        with pytest.raises(ValidationError) as excinfo:
            ApiPayload(data=[])
        
        error_msg = str(excinfo.value)
        assert "data" in error_msg
        
    def test_payload_without_options(self):
        """Test ApiPayload without options."""
        payload_data = {
            "data": [
                {
                    "ioc": {"type": "ip", "value": "1.2.3.4"},
                    "detection": {"type": "correlation"}
                }
            ]
        }
        
        payload = ApiPayload(**payload_data)
        assert payload.options is None


class TestValidatePayloadFunction:
    """Tests for the validate_payload function."""
    
    def test_validate_valid_payload(self):
        """Test validation of valid payload."""
        valid_payload = {
            "data": [
                {
                    "ioc": {"type": "ip", "value": "1.2.3.4"},
                    "detection": {"type": "correlation"},
                    "timestamp": "2023-01-01T10:00:00Z"
                }
            ],
            "options": {"debug": True}
        }
        
        error = validate_payload(valid_payload)
        assert error is None, f"Expected None but got: {error}"
    
    def test_validate_invalid_payload(self):
        """Test validation of invalid payload."""
        invalid_payloads = [
            # No data field
            {},
            # Empty data array
            {"data": []},
            # Invalid IoC type
            {
                "data": [
                    {
                        "ioc": {"type": "invalid", "value": "test"},
                        "detection": {"type": "correlation"}
                    }
                ]
            },
            # Missing IoC value
            {
                "data": [
                    {
                        "ioc": {"type": "ip"},
                        "detection": {"type": "correlation"}
                    }
                ]
            },
            # Invalid timestamp
            {
                "data": [
                    {
                        "ioc": {"type": "ip", "value": "1.2.3.4"},
                        "detection": {"type": "correlation"},
                        "timestamp": "invalid-timestamp"
                    }
                ]
            }
        ]
        
        for payload in invalid_payloads:
            error = validate_payload(payload)
            assert error is not None, f"Expected error for payload: {payload}"
    
    def test_validation_error_formatting(self):
        """Test the formatting of validation error messages."""
        invalid_payload = {
            "data": [
                {
                    "ioc": {"type": "ip"},  # Missing value
                    "detection": {"type": "correlation"}
                }
            ]
        }
        
        error = validate_payload(invalid_payload)
        assert error is not None
        assert "Validation error at " in error
        
    def test_multiple_validation_issues(self):
        """Test validation with multiple issues."""
        payload_with_multiple_issues = {
            "data": [
                {
                    "ioc": {"type": "invalid", "value": ""},
                    "detection": {"type": "detection_rule"}  # Missing sub_type
                }
            ]
        }
        
        error = validate_payload(payload_with_multiple_issues)
        assert error is not None
        # Only the first error should be returned
        assert "Validation error at " in error
    
    # Note: We're skipping the test for the "unknown validation error" case
    # where a ValidationError is raised but error.errors() returns an empty list,
    # as this is extremely rare and difficult to mock properly.