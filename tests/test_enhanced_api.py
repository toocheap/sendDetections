#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the enhanced API client with retry logic.
"""

import pytest
import json
import time
from unittest.mock import patch, MagicMock, Mock

import requests
from requests.exceptions import HTTPError, ConnectionError, Timeout

from sendDetections.enhanced_api_client import EnhancedApiClient
from sendDetections.errors import (
    ApiError, ApiAuthenticationError, ApiAccessDeniedError, ApiRateLimitError,
    ApiServerError, ApiClientError, ApiConnectionError, ApiTimeoutError,
    PayloadValidationError
)


# Test client initialization
def test_enhanced_api_client_init():
    """Test EnhancedApiClient initialization."""
    client = EnhancedApiClient(api_token="test_token")
    assert client.api_token == "test_token"
    assert client.max_retries == 3
    assert client.retry_delay == 1.0
    assert not client.silent
    
    # Test with custom values
    client = EnhancedApiClient(
        api_token="test_token",
        api_url="https://custom-api.example.com",
        max_retries=5,
        retry_delay=2.0,
        retry_status_codes=[429, 500],
        timeout=60,
        silent=True
    )
    assert client.api_token == "test_token"
    assert client.api_url == "https://custom-api.example.com"
    assert client.max_retries == 5
    assert client.retry_delay == 2.0
    assert client.retry_status_codes == [429, 500]
    assert client.timeout == 60
    assert client.silent


# Test validating payload with invalid data
def test_validate_invalid_payload():
    """Test payload validation with invalid data."""
    client = EnhancedApiClient(api_token="test_token")
    
    # Missing required fields
    invalid_payload = {"data": [{"not_valid": True}]}
    error = client.validate_payload(invalid_payload)
    assert error is not None
    
    # Valid payload
    valid_payload = {
        "data": [
            {
                "ioc": {
                    "type": "ip",
                    "value": "1.2.3.4"
                },
                "detection": {
                    "type": "playbook",
                    "id": "test-id"
                }
            }
        ]
    }
    error = client.validate_payload(valid_payload)
    assert error is None


# Test add_default_options method
def test_add_default_options():
    """Test add_default_options method."""
    client = EnhancedApiClient(api_token="test_token")
    
    # Test with empty payload
    payload_without_options = {"data": []}
    result = client.add_default_options(payload_without_options)
    assert "options" in result
    assert "debug" in result["options"]
    assert "summary" in result["options"]
    
    # Test with existing options
    payload_with_options = {
        "data": [],
        "options": {
            "debug": True,
            "summary": False
        }
    }
    result = client.add_default_options(payload_with_options)
    assert result["options"]["debug"] is True
    assert result["options"]["summary"] is False
    
    # Test with debug override
    result = client.add_default_options(payload_without_options, debug=True)
    assert result["options"]["debug"] is True


@patch('requests.post')
def test_send_data_success(mock_post):
    """Test successful API call with EnhancedApiClient."""
    # Setup mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "summary": {
            "submitted": 1,
            "processed": 1,
            "dropped": 0
        }
    }
    mock_post.return_value = mock_response
    
    # Create client and payload
    client = EnhancedApiClient(api_token="test_token")
    payload = {
        "data": [
            {
                "ioc": {
                    "type": "ip",
                    "value": "1.2.3.4"
                },
                "detection": {
                    "type": "playbook",
                    "id": "test-id"
                }
            }
        ]
    }
    
    # Make the API call
    result = client.send_data(payload)
    
    # Verify the result
    assert "summary" in result
    assert result["summary"]["submitted"] == 1
    assert result["summary"]["processed"] == 1
    assert result["summary"]["dropped"] == 0
    
    # Verify the request was made correctly
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == client.api_url  # First positional arg is URL
    assert "X-RFToken" in call_args[1]["headers"]
    assert call_args[1]["headers"]["X-RFToken"] == "test_token"
    assert call_args[1]["timeout"] == 30
    
    # Verify payload was transformed correctly
    sent_data = call_args[1]["json"]
    assert "options" in sent_data
    assert "data" in sent_data


@patch('requests.post')
def test_handle_http_error_401(mock_post):
    """Test handling of 401 HTTP error."""
    # Setup mock response
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"message": "Invalid API token"}
    mock_response.text = '{"message": "Invalid API token"}'
    error = requests.exceptions.HTTPError("401 Client Error")
    error.response = mock_response
    mock_post.side_effect = error
    
    # Create client and payload
    client = EnhancedApiClient(api_token="test_token", max_retries=0)
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Make the API call and expect an exception
    with pytest.raises(ApiAuthenticationError) as excinfo:
        client.send_data(payload)
    
    # Verify the exception details
    assert "Authentication failed" in str(excinfo.value)
    assert excinfo.value.status_code == 401


@patch('requests.post')
def test_handle_http_error_403(mock_post):
    """Test handling of 403 HTTP error."""
    # Setup mock response
    mock_response = Mock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"message": "Access denied"}
    mock_response.text = '{"message": "Access denied"}'
    error = requests.exceptions.HTTPError("403 Client Error")
    error.response = mock_response
    mock_post.side_effect = error
    
    # Create client and payload
    client = EnhancedApiClient(api_token="test_token", max_retries=0)
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Make the API call and expect an exception
    with pytest.raises(ApiAccessDeniedError) as excinfo:
        client.send_data(payload)
    
    # Verify the exception details
    assert "Access denied" in str(excinfo.value)
    assert excinfo.value.status_code == 403


@patch('requests.post')
def test_handle_http_error_429(mock_post):
    """Test handling of 429 HTTP error."""
    # Setup mock response
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.json.return_value = {"message": "Rate limit exceeded"}
    mock_response.text = '{"message": "Rate limit exceeded"}'
    mock_response.headers = {"Retry-After": "60"}
    error = requests.exceptions.HTTPError("429 Client Error")
    error.response = mock_response
    mock_post.side_effect = error
    
    # Create client and payload
    client = EnhancedApiClient(api_token="test_token", max_retries=0)
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Make the API call and expect an exception
    with pytest.raises(ApiRateLimitError) as excinfo:
        client.send_data(payload)
    
    # Verify the exception details
    assert "Rate limit exceeded" in str(excinfo.value)
    assert excinfo.value.status_code == 429
    assert excinfo.value.retry_after == 60


@patch('requests.post')
def test_handle_http_error_500(mock_post):
    """Test handling of 500 HTTP error."""
    # Setup mock response
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"message": "Internal server error"}
    mock_response.text = '{"message": "Internal server error"}'
    error = requests.exceptions.HTTPError("500 Server Error")
    error.response = mock_response
    mock_post.side_effect = error
    
    # Create client and payload
    client = EnhancedApiClient(api_token="test_token", max_retries=0)
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Make the API call and expect an exception
    with pytest.raises(ApiServerError) as excinfo:
        client.send_data(payload)
    
    # Verify the exception details
    assert "Server error" in str(excinfo.value)
    assert excinfo.value.status_code == 500


@patch('requests.post')
def test_handle_connection_error(mock_post):
    """Test handling of connection error."""
    # Setup mock error
    error = requests.exceptions.ConnectionError("Connection refused")
    mock_post.side_effect = error
    
    # Create client and payload
    client = EnhancedApiClient(api_token="test_token", max_retries=0)
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Make the API call and expect an exception
    with pytest.raises(ApiConnectionError) as excinfo:
        client.send_data(payload)
    
    # Verify the exception details
    assert "Connection" in str(excinfo.value)


@patch('requests.post')
def test_handle_timeout_error(mock_post):
    """Test handling of timeout error."""
    # Setup mock error
    error = requests.exceptions.Timeout("Request timed out")
    mock_post.side_effect = error
    
    # Create client and payload
    client = EnhancedApiClient(api_token="test_token", max_retries=0)
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Make the API call and expect an exception
    with pytest.raises(ApiTimeoutError) as excinfo:
        client.send_data(payload)
    
    # Verify the exception details
    assert "timed out" in str(excinfo.value)


@patch('requests.post')
def test_payload_validation_error(mock_post):
    """Test payload validation error."""
    # Create client and invalid payload
    client = EnhancedApiClient(api_token="test_token")
    payload = {
        "data": [
            {
                "invalid": "payload"  # Missing required fields
            }
        ]
    }
    
    # Make the API call and expect an exception
    with pytest.raises(PayloadValidationError) as excinfo:
        client.send_data(payload)
    
    # Verify the exception was raised before any HTTP request
    assert not mock_post.called
    assert "Payload validation failed" in str(excinfo.value)


@patch('requests.post')
@patch('time.sleep')  # Mock time.sleep to avoid waiting in tests
def test_retry_logic(mock_sleep, mock_post):
    """Test retry logic for retryable errors."""
    # Setup mock responses
    error_response = Mock()
    error_response.status_code = 500
    error_response.json.return_value = {"message": "Internal server error"}
    error_response.text = '{"message": "Internal server error"}'
    
    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "summary": {
            "submitted": 1,
            "processed": 1,
            "dropped": 0
        }
    }
    
    # First call raises an error, second succeeds
    error = requests.exceptions.HTTPError("500 Server Error")
    error.response = error_response
    mock_post.side_effect = [error, success_response]
    
    # Create client with retry enabled
    client = EnhancedApiClient(api_token="test_token", max_retries=3, retry_delay=0.1)
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Make the API call
    result = client.send_data(payload)
    
    # Verify the result comes from the second (successful) call
    assert "summary" in result
    assert result["summary"]["submitted"] == 1
    
    # Verify post was called twice and sleep was called once
    assert mock_post.call_count == 2
    assert mock_sleep.call_count == 1


@patch('requests.post')
@patch('time.sleep')  # Mock time.sleep to avoid waiting in tests
def test_max_retries_exceeded(mock_sleep, mock_post):
    """Test behavior when max retries are exceeded."""
    # Setup mock response
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"message": "Internal server error"}
    mock_response.text = '{"message": "Internal server error"}'
    
    # Create HTTP error
    error = requests.exceptions.HTTPError("500 Server Error")
    error.response = mock_response
    
    # Make post always fail
    mock_post.side_effect = error
    
    # Create client with 2 retries
    client = EnhancedApiClient(api_token="test_token", max_retries=2, retry_delay=0.1)
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Make the API call and expect exception after retries
    with pytest.raises(ApiServerError) as excinfo:
        client.send_data(payload)
    
    # Verify the exception details
    assert "Server error" in str(excinfo.value)
    assert excinfo.value.status_code == 500
    
    # Verify post was called 3 times (initial + 2 retries) and sleep twice
    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 2


def test_batch_send():
    """Test batch_send method."""
    # Create client
    client = EnhancedApiClient(api_token="test_token")
    
    # Create test payloads
    payloads = [
        {
            "data": [
                {
                    "ioc": {"type": "ip", "value": "1.2.3.4"},
                    "detection": {"type": "playbook", "id": "test-id-1"}
                }
            ]
        },
        {
            "data": [
                {
                    "ioc": {"type": "ip", "value": "5.6.7.8"},
                    "detection": {"type": "playbook", "id": "test-id-2"}
                }
            ]
        }
    ]
    
    # Mock send_data to return expected responses
    client.send_data = MagicMock(side_effect=[
        {"summary": {"submitted": 1, "processed": 1, "dropped": 0}},
        {"summary": {"submitted": 1, "processed": 1, "dropped": 0}}
    ])
    
    # Call batch_send
    results = client.batch_send(payloads)
    
    # Verify results
    assert len(results) == 2
    assert results[0]["summary"]["submitted"] == 1
    assert results[1]["summary"]["submitted"] == 1
    
    # Verify send_data was called with each payload
    assert client.send_data.call_count == 2
    client.send_data.assert_any_call(payloads[0], debug=False)
    client.send_data.assert_any_call(payloads[1], debug=False)


def test_batch_send_with_exception():
    """Test batch_send method with an exception."""
    # Create client
    client = EnhancedApiClient(api_token="test_token")
    
    # Create test payloads
    payloads = [
        {
            "data": [
                {
                    "ioc": {"type": "ip", "value": "1.2.3.4"},
                    "detection": {"type": "playbook", "id": "test-id-1"}
                }
            ]
        },
        {
            "data": [
                {
                    "ioc": {"type": "ip", "value": "5.6.7.8"},
                    "detection": {"type": "playbook", "id": "test-id-2"}
                }
            ]
        }
    ]
    
    # Mock send_data to return a success and then raise an exception
    success_response = {"summary": {"submitted": 1, "processed": 1, "dropped": 0}}
    error = ApiServerError("Server error", 500)
    client.send_data = MagicMock(side_effect=[success_response, error])
    
    # Call batch_send
    results = client.batch_send(payloads, continue_on_error=True)
    
    # Verify results
    assert len(results) == 2
    assert results[0]["summary"]["submitted"] == 1
    assert "error" in results[1]
    assert "Server error" in results[1]["error"]
    
    # Verify send_data was called with each payload
    assert client.send_data.call_count == 2
    
    # Test with continue_on_error=False (default)
    client.send_data = MagicMock(side_effect=[success_response, error])
    
    # Should raise the exception on the second payload
    with pytest.raises(ApiServerError) as excinfo:
        client.batch_send(payloads)
    
    # Verify the exception details
    assert "Server error" in str(excinfo.value)
    assert client.send_data.call_count == 2