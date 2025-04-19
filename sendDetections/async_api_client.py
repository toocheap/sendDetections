#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Asynchronous API client for Recorded Future Collective Insights Detection API.
Provides non-blocking I/O for improved performance with bulk operations.
Uses Python 3.10+ type annotations.
"""

import asyncio
import logging
import time
from typing import Any, Optional, cast
from collections.abc import Mapping, Sequence

import aiohttp
from pydantic import ValidationError

from sendDetections.config import API_URL, DEFAULT_HEADERS, DEFAULT_API_OPTIONS
from sendDetections.validators import validate_payload, ApiPayload
from sendDetections.errors import (
    ApiError, ApiAuthenticationError, ApiAccessDeniedError, 
    ApiRateLimitError, ApiServerError, ApiClientError,
    ApiConnectionError, ApiTimeoutError, PayloadValidationError
)

# Configure logger
logger = logging.getLogger(__name__)

class AsyncApiClient:
    """
    Asynchronous client for sending data to Recorded Future Collective Insights Detection API.
    Uses aiohttp for non-blocking HTTP requests.
    """

    def __init__(
        self, 
        api_token: str, 
        api_url: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
        retry_status_codes: Optional[list[int]] = None,
        max_concurrent: int = 5
    ):
        """
        Initialize the async API client.
        
        Args:
            api_token: Recorded Future API token
            api_url: Optional custom API URL (overrides config)
            max_retries: Maximum number of retry attempts for retryable errors
            retry_delay: Base delay between retries in seconds (uses exponential backoff)
            timeout: Request timeout in seconds
            retry_status_codes: HTTP status codes to retry (defaults to [429, 500, 502, 503, 504])
            max_concurrent: Maximum number of concurrent requests
        """
        self.api_token = api_token
        self.api_url = api_url or API_URL
        self.headers = {**DEFAULT_HEADERS, "X-RFToken": api_token}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        
        # Default to common retryable status codes if none specified
        self.retry_status_codes = retry_status_codes or [429, 500, 502, 503, 504]
        
        # Semaphore to limit concurrent requests
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        logger.debug("AsyncApiClient initialized with URL: %s", self.api_url)
    
    @staticmethod
    def validate_payload(payload: Mapping[str, Any]) -> Optional[str]:
        """
        Validate a payload dict. Returns an error message if invalid, else None.
        """
        return validate_payload(payload)

    def add_default_options(self, payload: Mapping[str, Any], debug: bool = False) -> dict[str, Any]:
        """
        Add default options to payload if not present.
        
        Args:
            payload: The API payload to augment
            debug: Whether to enable debug mode (overrides payload)
            
        Returns:
            Updated payload with options
        """
        # Make a copy to avoid modifying the original
        result = dict(payload)
        
        # Apply DEFAULT_API_OPTIONS if options not present
        if "options" not in result:
            result["options"] = DEFAULT_API_OPTIONS.copy()
            
        # Override debug flag if specified
        if debug:
            if "options" not in result:
                result["options"] = {}
            result["options"]["debug"] = True
            
        return result
    
    async def _handle_http_error(self, status_code: int, response_text: str, response_headers: Mapping[str, str]) -> None:
        """
        Handle HTTP errors by raising appropriate typed exceptions.
        
        Args:
            status_code: HTTP status code
            response_text: Response body text
            response_headers: Response headers
            
        Raises:
            ApiAuthenticationError: 401 errors
            ApiAccessDeniedError: 403 errors
            ApiRateLimitError: 429 errors
            ApiServerError: 5xx errors
            ApiClientError: Other 4xx errors
        """
        # Try to parse error JSON
        error_data = {}
        try:
            import json
            error_data = json.loads(response_text)
            error_msg = error_data.get("message", response_text)
        except (ValueError, KeyError):
            error_msg = response_text
        
        # Extract retry-after header for rate limiting
        retry_after = None
        if status_code == 429 and "Retry-After" in response_headers:
            try:
                retry_after = int(response_headers["Retry-After"])
            except (ValueError, TypeError):
                pass
        
        # Raise the appropriate typed exception based on status code
        if status_code == 401:
            logger.error("Authentication failed: %s", error_msg)
            raise ApiAuthenticationError(f"Authentication failed: {error_msg}", 
                                       status_code, error_data)
        elif status_code == 403:
            logger.error("Access denied: %s", error_msg)
            raise ApiAccessDeniedError(f"Access denied: {error_msg}", 
                                      status_code, error_data)
        elif status_code == 429:
            logger.warning("Rate limit exceeded: %s (retry after: %s seconds)", 
                          error_msg, retry_after or "unknown")
            raise ApiRateLimitError(f"Rate limit exceeded: {error_msg}", 
                                   status_code, error_data, retry_after)
        elif 500 <= status_code < 600:
            logger.error("Server error: %s", error_msg)
            raise ApiServerError(f"Server error ({status_code}): {error_msg}", 
                                status_code, error_data)
        else:
            logger.error("API error: %s", error_msg)
            raise ApiClientError(f"API error ({status_code}): {error_msg}", 
                               status_code, error_data)
    
    async def send_data(
        self, 
        payload: Mapping[str, Any], 
        debug: bool = False, 
        retry: bool = True
    ) -> dict[str, Any]:
        """
        Send data to the API with automatic retries for certain errors.
        
        Args:
            payload: The data payload to send
            debug: Whether to enable debug mode
            retry: Whether to retry on retryable errors
            
        Returns:
            API response as a dictionary
            
        Raises:
            PayloadValidationError: On invalid payload structure
            ApiAuthenticationError: On authentication failures
            ApiAccessDeniedError: On authorization failures
            ApiRateLimitError: On rate limit exceeded
            ApiServerError: On server errors (5xx)
            ApiClientError: On client errors (4xx)
            ApiConnectionError: On connection issues
            ApiTimeoutError: On request timeout
        """
        # Pre-send validation
        if (error := validate_payload(payload)):
            raise PayloadValidationError(f"Payload validation failed: {error}")

        # Apply default options and debug flag
        payload_dict = self.add_default_options(payload, debug)
        
        # For readable logging, show count of IOCs
        ioc_count = len(payload_dict.get("data", []))
        logger.info("Sending %d detection(s) to %s (debug=%s)", 
                   ioc_count, self.api_url, payload_dict.get("options", {}).get("debug", False))
        
        # Initialize retry counter and track attempts
        attempts = 0
        last_error = None
        
        # Create the semaphore if it doesn't exist
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Acquire semaphore to limit concurrent requests
        async with self._semaphore:
            # Set timeout for the request
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            while attempts <= self.max_retries:
                # Create a new ClientSession for each attempt
                # This ensures we don't reuse connections that might be problematic
                try:
                    # Only log retry attempts after the first attempt
                    if attempts > 0:
                        logger.info("Retry attempt %d of %d", attempts, self.max_retries)
                    
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post(
                            self.api_url,
                            headers=self.headers,
                            json=payload_dict
                        ) as response:
                            # Check for HTTP errors
                            if response.status >= 400:
                                text = await response.text()
                                await self._handle_http_error(
                                    response.status, 
                                    text, 
                                    response.headers
                                )
                            
                            # Attempt to parse response as JSON
                            try:
                                result = await response.json()
                                
                                # Log success with summary if available
                                if "summary" in result:
                                    summary = result["summary"]
                                    logger.info("API call successful: %d submitted, %d processed, %d dropped",
                                              summary.get("submitted", 0), 
                                              summary.get("processed", 0),
                                              summary.get("dropped", 0))
                                else:
                                    logger.info("API call successful")
                                    
                                return cast(dict[str, Any], result)
                            except ValueError as e:
                                logger.warning("Could not parse API response as JSON: %s", str(e))
                                # Return empty dict if we can't parse the response
                                return {}
                
                except aiohttp.ClientResponseError as e:
                    last_error = e
                    status_code = e.status
                    
                    # Check if we should retry based on status code
                    if retry and status_code in self.retry_status_codes and attempts < self.max_retries:
                        # For rate limit errors, use the Retry-After header if available
                        if status_code == 429 and "Retry-After" in e.headers:
                            try:
                                delay = int(e.headers["Retry-After"])
                                logger.info("Rate limited. Waiting %d seconds before retry.", delay)
                                await asyncio.sleep(delay)
                            except (ValueError, TypeError):
                                # If Retry-After header is invalid, use exponential backoff
                                delay = self.retry_delay * (2 ** attempts)
                                logger.info("Rate limited. Using exponential backoff: waiting %.1f seconds", delay)
                                await asyncio.sleep(delay)
                        else:
                            # Use exponential backoff for other retryable errors
                            delay = self.retry_delay * (2 ** attempts)
                            logger.info("Retryable error (status=%d). Waiting %.1f seconds", status_code, delay)
                            await asyncio.sleep(delay)
                        
                        attempts += 1
                        continue
                    else:
                        # If not retrying or max retries reached, convert to appropriate exception
                        if status_code == 401:
                            raise ApiAuthenticationError(str(e), status_code)
                        elif status_code == 403:
                            raise ApiAccessDeniedError(str(e), status_code)
                        elif status_code == 429:
                            raise ApiRateLimitError(str(e), status_code)
                        elif 500 <= status_code < 600:
                            raise ApiServerError(str(e), status_code)
                        else:
                            raise ApiClientError(str(e), status_code)
                
                except asyncio.TimeoutError as e:
                    last_error = e
                    logger.warning("Request timed out after %.1f seconds", self.timeout)
                    
                    if retry and attempts < self.max_retries:
                        delay = self.retry_delay * (2 ** attempts)
                        logger.info("Retrying after timeout. Waiting %.1f seconds", delay)
                        await asyncio.sleep(delay)
                        attempts += 1
                        continue
                    else:
                        raise ApiTimeoutError(f"Request timed out after {self.timeout} seconds")
                
                except aiohttp.ClientConnectorError as e:
                    last_error = e
                    logger.warning("Connection error: %s", str(e))
                    
                    if retry and attempts < self.max_retries:
                        delay = self.retry_delay * (2 ** attempts)
                        logger.info("Retrying after connection error. Waiting %.1f seconds", delay)
                        await asyncio.sleep(delay)
                        attempts += 1
                        continue
                    else:
                        raise ApiConnectionError(f"Connection failed: {str(e)}")
                
                except Exception as e:
                    # Unexpected errors won't be retried
                    logger.error("Unexpected error: %s", str(e), exc_info=True)
                    raise ApiError(f"Unexpected error: {str(e)}")
            
            # If we've exhausted retries, re-raise the last error
            if isinstance(last_error, aiohttp.ClientResponseError):
                status_code = getattr(last_error, 'status', 0)
                if status_code == 401:
                    raise ApiAuthenticationError(str(last_error), status_code)
                elif status_code == 403:
                    raise ApiAccessDeniedError(str(last_error), status_code)
                elif status_code == 429:
                    raise ApiRateLimitError(str(last_error), status_code)
                elif 500 <= status_code < 600:
                    raise ApiServerError(str(last_error), status_code)
                else:
                    raise ApiClientError(str(last_error), status_code)
            elif isinstance(last_error, asyncio.TimeoutError):
                raise ApiTimeoutError(f"Request timed out after {self.max_retries} retries")
            elif isinstance(last_error, aiohttp.ClientConnectorError):
                raise ApiConnectionError(f"Connection failed after {self.max_retries} retries: {str(last_error)}")
            else:
                raise ApiError(f"Failed after {self.max_retries} retries: {str(last_error) if last_error else 'Unknown error'}")
    
    async def batch_send(
        self, 
        payloads: Sequence[Mapping[str, Any]], 
        debug: bool = False,
        retry: bool = True,
        return_exceptions: bool = False
    ) -> list[dict[str, Any] | Exception]:
        """
        Send multiple payloads concurrently.
        
        Args:
            payloads: List of payload dicts to send
            debug: Whether to enable debug mode for all payloads
            retry: Whether to retry failed requests
            return_exceptions: If True, include exceptions in results instead of raising
            
        Returns:
            List of API responses or exceptions if return_exceptions is True
            
        Raises:
            ApiError or subclasses if any request fails and return_exceptions is False
        """
        if not payloads:
            return []
            
        # Create tasks for each payload
        tasks = [
            self.send_data(payload, debug=debug, retry=retry)
            for payload in payloads
        ]
        
        # Gather results, optionally capturing exceptions
        if return_exceptions:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        else:
            # This will raise the first exception encountered
            results = await asyncio.gather(*tasks)
            return results

    async def split_and_send(
        self, 
        payload: Mapping[str, Any], 
        batch_size: int = 100,
        debug: bool = False,
        retry: bool = True
    ) -> dict[str, Any]:
        """
        Split a large payload into smaller batches and send them concurrently.
        
        Args:
            payload: The payload dict to split and send
            batch_size: Maximum entries per batch
            debug: Whether to enable debug mode
            retry: Whether to retry failed requests
            
        Returns:
            Merged responses with combined summary
            
        Raises:
            PayloadValidationError: On invalid payload structure
            ApiError or subclasses: On API errors
        """
        # Validate the original payload
        if (error := validate_payload(payload)):
            raise PayloadValidationError(f"Payload validation failed: {error}")
            
        # Extract data entries
        data = payload.get("data", [])
        if not data:
            # Nothing to send
            return {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
            
        # Get a clean copy of the payload without data
        base_payload = dict(payload)
        base_payload.pop("data", None)
        
        # Split data into batches
        total_entries = len(data)
        batches = []
        
        for i in range(0, total_entries, batch_size):
            # Create a new payload with a subset of data
            batch_payload = dict(base_payload)
            batch_payload["data"] = data[i:i+batch_size]
            batches.append(batch_payload)
            
        # Send batches concurrently
        logger.info("Splitting payload with %d entries into %d batches of max %d entries",
                   total_entries, len(batches), batch_size)
                   
        results = await self.batch_send(batches, debug=debug, retry=retry)
        
        # Merge results
        merged_result: dict[str, Any] = {"summary": {"submitted": 0, "processed": 0, "dropped": 0}}
        
        for result in results:
            if "summary" in result:
                summary = result["summary"]
                merged_result["summary"]["submitted"] += summary.get("submitted", 0)
                merged_result["summary"]["processed"] += summary.get("processed", 0)
                merged_result["summary"]["dropped"] += summary.get("dropped", 0)
                
        logger.info("Completed batch processing: %d submitted, %d processed, %d dropped",
                   merged_result["summary"]["submitted"],
                   merged_result["summary"]["processed"],
                   merged_result["summary"]["dropped"])
                   
        return merged_result