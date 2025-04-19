"""
Property-based tests for sendDetections using Hypothesis.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, List, Any

import pytest
from hypothesis import given, settings, strategies as st

from sendDetections.csv_converter import CSVConverter, CSVConversionError 
from sendDetections.validators import validate_payload
from sendDetections.api_client import DetectionApiClient

# Define strategies for different data types
ioc_types = st.sampled_from(["ip", "domain", "hash", "vulnerability", "url"])
detection_types = st.sampled_from(["correlation", "playbook", "detection_rule", "sandbox"])
detection_subtypes = st.sampled_from(["sigma", "yara", "snort"])

# Strategy for RFC 3339 timestamps
rfc3339_timestamps = st.datetimes().map(
    lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
)

# Strategy for IP addresses (simplified)
ip_addresses = st.tuples(
    st.integers(min_value=1, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=1, max_value=255)
).map(lambda parts: f"{parts[0]}.{parts[1]}.{parts[2]}.{parts[3]}")

# Strategy for domain names (simplified)
domain_names = st.text(
    alphabet=st.characters(whitelist_categories=('Ll',), whitelist_characters='-'),
    min_size=3, max_size=15
).map(lambda s: f"{s}.com")

# Strategy for generating valid IoC values based on type
@st.composite
def ioc_values(draw, ioc_type=None):
    if ioc_type is None:
        ioc_type = draw(ioc_types)
        
    if ioc_type == "ip":
        return draw(ip_addresses)
    elif ioc_type == "domain":
        return draw(domain_names)
    elif ioc_type == "hash":
        return draw(st.text(alphabet='0123456789abcdef', min_size=32, max_size=64))
    elif ioc_type == "url":
        domain = draw(domain_names)
        path = draw(st.text(min_size=0, max_size=20))
        return f"https://{domain}/{path}"
    elif ioc_type == "vulnerability":
        return draw(st.text(
            alphabet='CVE-',
            min_size=4,
            max_size=4
        ).map(lambda s: s + draw(st.integers(min_value=1990, max_value=2023).map(str)) + '-' +
             draw(st.integers(min_value=1, max_value=99999).map(lambda n: f"{n:05d}"))))
    
    return draw(st.text(min_size=1, max_size=30))

# Strategy for generating valid detection entries
@st.composite
def detection_entries(draw):
    det_type = draw(detection_types)
    entry = {
        "type": det_type,
        "name": draw(st.text(min_size=1, max_size=30))
    }
    
    # Add required sub_type for detection_rule
    if det_type == "detection_rule":
        entry["sub_type"] = draw(detection_subtypes)
        
    # Optionally add ID
    if draw(st.booleans()):
        entry["id"] = draw(st.text(min_size=5, max_size=20))
        
    return entry

# Strategy for generating valid IoC entries
@st.composite
def ioc_entries(draw):
    ioc_type = draw(ioc_types)
    return {
        "type": ioc_type,
        "value": draw(ioc_values(ioc_type))
    }

# Strategy for generating valid data entries
@st.composite
def data_entries(draw):
    entry = {
        "ioc": draw(ioc_entries()),
        "detection": draw(detection_entries()),
    }
    
    # Add optional fields
    if draw(st.booleans()):
        entry["timestamp"] = draw(rfc3339_timestamps)
        
    if draw(st.booleans()):
        entry["mitre_codes"] = draw(st.lists(
            st.text(alphabet="T", min_size=1, max_size=1).map(
                lambda s: s + draw(st.integers(min_value=1000, max_value=9999).map(str))
            ),
            min_size=0, max_size=3
        ))
        
    if draw(st.booleans()):
        entry["malwares"] = draw(st.lists(
            st.text(min_size=3, max_size=15),
            min_size=0, max_size=3
        ))
        
    return entry

# Strategy for generating a valid API payload
@st.composite
def valid_payloads(draw):
    return {
        "data": draw(st.lists(data_entries(), min_size=1, max_size=5)),
        "options": {
            "debug": draw(st.booleans()),
            "summary": draw(st.booleans())
        }
    }

# Property: All valid payloads should pass validation
@given(payload=valid_payloads())
def test_valid_payload_validation(payload):
    """Test that generated valid payloads pass validation."""
    error = validate_payload(payload)
    assert error is None, f"Valid payload failed validation: {error}"

# Property: DetectionApiClient should correctly add options to payloads
@given(
    payload=valid_payloads(),
    debug_override=st.booleans()
)
def test_api_client_add_default_options(payload, debug_override):
    """Test that DetectionApiClient correctly adds default options."""
    client = DetectionApiClient("dummy-token")
    
    # Make a copy to avoid modifying the original
    original_options = payload.get("options", {}).copy()
    
    # Apply options
    updated = client.add_default_options(payload, debug=debug_override)
    
    # Assert options were added correctly
    assert "options" in updated
    
    # Check that debug was overridden if specified
    if debug_override:
        assert updated["options"]["debug"] is True
    # If not overriding debug, the original value should be preserved
    elif "options" in payload and "debug" in payload["options"]:
        assert updated["options"]["debug"] == original_options.get("debug")