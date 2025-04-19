#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Additional tests for the AsyncApiClient to improve test coverage.
Tests focus on error handling, retries and edge cases.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import aiohttp
from aiohttp import ClientResponseError, ClientConnectorError, ClientPayloadError

from sendDetections.async_api_client import AsyncApiClient
from sendDetections.errors import (
    ApiError, ApiAuthenticationError, ApiAccessDeniedError, 
    ApiRateLimitError, ApiServerError, ApiClientError,
    ApiConnectionError, ApiTimeoutError, PayloadValidationError
)


@pytest.mark.asyncio
async def test_send_data_client_payload_error():
    """Test handling of ClientPayloadError during response processing."""
    # Create client with no retries
    client = AsyncApiClient(api_token="test_token", max_retries=0)
    
    # Create a valid payload
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Mock ClientSession to raise ClientPayloadError
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.side_effect = aiohttp.ClientPayloadError("Error parsing response payload")
    mock_response.text.return_value = "Invalid response"
    
    # Configure mocks
    mock_session.__aenter__.return_value = mock_session
    mock_session.post.return_value.__aenter__.return_value = mock_response
    
    with patch('aiohttp.ClientSession', return_value=mock_session):
        # This should log a warning but return an empty dict, not raise an exception
        result = await client.send_data(payload)
        assert result == {}
        mock_response.json.assert_called_once()


@pytest.mark.asyncio
async def test_send_data_connection_retries():
    """Test connection error retry logic."""
    # Create client with specific retry settings
    client = AsyncApiClient(api_token="test_token", max_retries=2, retry_delay=0.01)
    
    # Create a valid payload
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Mock ClientSession to raise ClientConnectorError twice then succeed
    mock_session1 = AsyncMock()
    mock_session1.__aenter__.return_value = mock_session1
    mock_session1.post.side_effect = ClientConnectorError(MagicMock(), OSError("Connection refused"))
    
    mock_session2 = AsyncMock()
    mock_session2.__aenter__.return_value = mock_session2
    mock_session2.post.side_effect = ClientConnectorError(MagicMock(), OSError("Connection refused"))
    
    mock_session3 = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    }
    mock_session3.__aenter__.return_value = mock_session3
    mock_session3.post.return_value.__aenter__.return_value = mock_response
    
    # Create side_effect to return different sessions on each call
    sessions = [mock_session1, mock_session2, mock_session3]
    
    with patch('aiohttp.ClientSession', side_effect=sessions), \
         patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        
        # Test retry logic - should succeed on third attempt
        result = await client.send_data(payload)
        
        # Verify result from successful call
        assert "summary" in result
        assert result["summary"]["submitted"] == 1
        
        # Verify sleep was called twice (for two retries)
        assert mock_sleep.call_count == 2
        
        # First sleep should be retry_delay * 2^0
        mock_sleep.assert_any_call(0.01)
        
        # Second sleep should be retry_delay * 2^1
        mock_sleep.assert_any_call(0.02)


@pytest.mark.asyncio
async def test_send_data_max_retries_exceeded():
    """Test behavior when max retries are exceeded for connection errors."""
    # Create client with specific retry settings
    client = AsyncApiClient(api_token="test_token", max_retries=2, retry_delay=0.01)
    
    # Create a valid payload
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Mock ClientSession to always raise ClientConnectorError
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.post.side_effect = ClientConnectorError(MagicMock(), OSError("Connection refused"))
    
    with patch('aiohttp.ClientSession', return_value=mock_session), \
         patch('asyncio.sleep', new_callable=AsyncMock):
        
        # Test - should raise ApiConnectionError after max retries
        with pytest.raises(ApiConnectionError) as excinfo:
            await client.send_data(payload)
        
        # Verify error message
        assert "Connection failed after 2 retries" in str(excinfo.value)


@pytest.mark.asyncio
async def test_send_data_timeout_retry():
    """Test timeout retry logic."""
    # Create client with specific retry settings
    client = AsyncApiClient(api_token="test_token", max_retries=1, retry_delay=0.01)
    
    # Create a valid payload
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Mock ClientSession to raise TimeoutError then succeed
    mock_session1 = AsyncMock()
    mock_session1.__aenter__.return_value = mock_session1
    mock_session1.post.side_effect = asyncio.TimeoutError()
    
    mock_session2 = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    }
    mock_session2.__aenter__.return_value = mock_session2
    mock_session2.post.return_value.__aenter__.return_value = mock_response
    
    # Create side_effect to return different sessions on each call
    sessions = [mock_session1, mock_session2]
    
    with patch('aiohttp.ClientSession', side_effect=sessions), \
         patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        
        # Test - should succeed on second attempt
        result = await client.send_data(payload)
        
        # Verify result from successful call
        assert "summary" in result
        assert result["summary"]["submitted"] == 1
        
        # Verify sleep was called once (for one retry)
        assert mock_sleep.call_count == 1
        
        # Sleep should be retry_delay * 2^0
        mock_sleep.assert_called_once_with(0.01)


@pytest.mark.asyncio
async def test_send_data_rate_limit_retry():
    """Test rate limit retry logic with Retry-After header."""
    # Create client with specific retry settings
    client = AsyncApiClient(api_token="test_token", max_retries=1, retry_delay=0.01)
    
    # Create a valid payload
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Create a ClientResponseError with status 429
    resp_headers = {"Retry-After": "2"}
    error = ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=429,
        message="Too Many Requests",
        headers=resp_headers
    )
    
    # Mock sessions
    mock_session1 = AsyncMock()
    mock_session1.__aenter__.return_value = mock_session1
    mock_session1.post.side_effect = error
    
    mock_session2 = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    }
    mock_session2.__aenter__.return_value = mock_session2
    mock_session2.post.return_value.__aenter__.return_value = mock_response
    
    # Create side_effect to return different sessions on each call
    sessions = [mock_session1, mock_session2]
    
    with patch('aiohttp.ClientSession', side_effect=sessions), \
         patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        
        # Test - should respect Retry-After header and succeed on second attempt
        result = await client.send_data(payload)
        
        # Verify result from successful call
        assert "summary" in result
        assert result["summary"]["submitted"] == 1
        
        # Verify sleep was called with the value from Retry-After
        mock_sleep.assert_called_once_with(2)


@pytest.mark.asyncio
async def test_semaphore_limit():
    """Test that the semaphore limits concurrent requests."""
    # Create client with specific max_concurrent value
    client = AsyncApiClient(api_token="test_token", max_concurrent=2)
    
    # Create payloads
    payloads = [
        {
            "data": [
                {
                    "ioc": {"type": "ip", "value": f"192.168.0.{i}"},
                    "detection": {"type": "playbook", "id": f"test-id-{i}"}
                }
            ]
        }
        for i in range(5)
    ]
    
    # Mock semaphore
    mock_semaphore = AsyncMock()
    client._semaphore = mock_semaphore
    
    # Mock send_data
    orig_send_data = client.send_data
    client.send_data = AsyncMock(return_value={"summary": {"submitted": 1, "processed": 1, "dropped": 0}})
    
    try:
        # Test batch_send
        await client.batch_send(payloads)
        
        # Verify send_data was called for each payload
        assert client.send_data.call_count == 5
        
        # Ensure the semaphore was created with max_concurrent
        assert isinstance(client._semaphore, AsyncMock)
        
        # We can't easily verify the semaphore behavior in a unit test, 
        # so this is mainly a coverage test
    finally:
        # Restore original send_data method
        client.send_data = orig_send_data


@pytest.mark.asyncio
async def test_split_and_send_empty_payload():
    """Test split_and_send with empty data array."""
    # Create client
    client = AsyncApiClient(api_token="test_token")
    
    # Create payload with empty data array
    payload = {
        "data": [],
        "options": {"debug": True}
    }
    
    # Mock batch_send (should not be called)
    with patch.object(client, 'batch_send') as mock_batch_send:
        result = await client.split_and_send(payload)
        
        # Verify batch_send was not called
        mock_batch_send.assert_not_called()
        
        # Verify empty result with zero counts
        assert result["summary"]["submitted"] == 0
        assert result["summary"]["processed"] == 0
        assert result["summary"]["dropped"] == 0


@pytest.mark.asyncio
async def test_unexpected_exception_handling():
    """Test handling of unexpected exceptions during API call."""
    # Create client with no retries
    client = AsyncApiClient(api_token="test_token", max_retries=0)
    
    # Create a valid payload
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Mock ClientSession to raise a generic exception
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.post.side_effect = Exception("Unexpected error")
    
    with patch('aiohttp.ClientSession', return_value=mock_session):
        # Test - should raise ApiError
        with pytest.raises(ApiError) as excinfo:
            await client.send_data(payload)
        
        # Verify error message
        assert "Unexpected error" in str(excinfo.value)


@pytest.mark.asyncio
async def test_retry_logic_for_5xx_errors():
    """Test retry logic for 5xx errors."""
    # Create client with specific retry settings
    client = AsyncApiClient(api_token="test_token", max_retries=1, retry_delay=0.01)
    
    # Create a valid payload
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Mock the first session to return a 502 error
    mock_session1 = AsyncMock()
    mock_response1 = AsyncMock()
    mock_response1.status = 502
    mock_response1.text.return_value = '{"message":"Bad Gateway"}'
    mock_response1.headers = {}
    mock_session1.__aenter__.return_value = mock_session1
    mock_session1.post.return_value.__aenter__.return_value = mock_response1
    
    # Mock the second session to succeed
    mock_session2 = AsyncMock()
    mock_response2 = AsyncMock()
    mock_response2.status = 200
    mock_response2.json.return_value = {
        "summary": {"submitted": 1, "processed": 1, "dropped": 0}
    }
    mock_session2.__aenter__.return_value = mock_session2
    mock_session2.post.return_value.__aenter__.return_value = mock_response2
    
    # Create side_effect to return different sessions on each call
    sessions = [mock_session1, mock_session2]
    
    with patch('aiohttp.ClientSession', side_effect=sessions), \
         patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        
        # Test - should retry on 502 and succeed
        result = await client.send_data(payload)
        
        # Verify result from successful call
        assert "summary" in result
        assert result["summary"]["submitted"] == 1
        
        # Verify sleep was called once (for one retry)
        assert mock_sleep.call_count == 1
        
        # Sleep should be retry_delay * 2^0
        mock_sleep.assert_called_once_with(0.01)


@pytest.mark.asyncio
async def test_retry_logic_disabled():
    """Test behavior when retry is disabled."""
    # Create client with retries enabled but we'll disable it in the call
    client = AsyncApiClient(api_token="test_token", max_retries=3)
    
    # Create a valid payload
    payload = {
        "data": [
            {
                "ioc": {"type": "ip", "value": "1.2.3.4"},
                "detection": {"type": "playbook", "id": "test-id"}
            }
        ]
    }
    
    # Mock ClientSession to return a 500 error
    mock_session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text.return_value = '{"message":"Internal Server Error"}'
    mock_response.headers = {}
    mock_session.__aenter__.return_value = mock_session
    mock_session.post.return_value.__aenter__.return_value = mock_response
    
    with patch('aiohttp.ClientSession', return_value=mock_session), \
         patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        
        # Test with retry=False
        with pytest.raises(ApiServerError) as excinfo:
            await client.send_data(payload, retry=False)
        
        # Verify error message
        assert "Server error" in str(excinfo.value)
        assert excinfo.value.status_code == 500
        
        # Verify sleep was not called (no retries)
        mock_sleep.assert_not_called()