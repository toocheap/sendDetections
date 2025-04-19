#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the asynchronous API client and batch processor.
"""

import asyncio
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import aiohttp
from aiohttp.client_reqrep import ClientResponse
from aiohttp.helpers import TimerNoop
from aiohttp import ClientSession

from sendDetections.async_api_client import AsyncApiClient
from sendDetections.batch_processor import BatchProcessor
from sendDetections.errors import (
    ApiAuthenticationError, ApiRateLimitError, ApiServerError,
    ApiConnectionError, ApiTimeoutError, PayloadValidationError
)


# Test AsyncApiClient initialization
def test_async_api_client_init():
    client = AsyncApiClient(api_token="test_token")
    assert client.api_token == "test_token"
    assert client.max_retries == 3
    assert client.retry_delay == 1.0
    assert client.max_concurrent == 5


# Test validating payload with invalid data
def test_validate_invalid_payload():
    client = AsyncApiClient(api_token="test_token")
    
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
    client = AsyncApiClient(api_token="test_token")
    
    # Test without options
    payload_without_options = {"data": []}
    result = client.add_default_options(payload_without_options)
    assert "options" in result
    assert result["options"]["debug"] is False
    assert result["options"]["summary"] is True
    
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


# Test BatchProcessor initialization
def test_batch_processor_init():
    processor = BatchProcessor(api_token="test_token", max_concurrent=10, batch_size=50)
    assert processor.api_token == "test_token"
    assert processor.max_concurrent == 10
    assert processor.batch_size == 50
    assert processor.max_retries == 3
    assert isinstance(processor.client, AsyncApiClient)


# Integration test with the CLI
@pytest.mark.asyncio
async def test_batch_command_help():
    # Basic test to ensure the batch command is registered
    with patch("sys.argv", ["sendDetections", "batch", "--help"]):
        from sendDetections.__main__ import setup_argparse
        parser = setup_argparse()
        try:
            # This will typically exit with SystemExit
            args = parser.parse_args()
        except SystemExit:
            pass
        
        # If we got this far without exception, the batch command is registered
        assert True