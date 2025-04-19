#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced API client for Recorded Future Collective Insights Detection API.
Adds retry logic, improved error handling, and structured logging.
Uses Python 3.10+ type annotations.
"""

import logging
import time
# Use standard library typing (Python 3.10+)
from typing import Any, Optional, cast
# Collections
from collections.abc import Sequence, Mapping

import requests
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

class EnhancedApiClient:
    """
    Enhanced client for sending data to Recorded Future Collective Insights Detection API.
    Includes retry logic, structured logging, and more specific error handling.
    """

    def __init__(
        self, 
        api_token: str, 
        api_url: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
        retry_status_codes: Optional[list[int]] = None,
        silent: bool = False
    ):
        """
        Initialize the enhanced API client.
        
        Args:
            api_token: Recorded Future API token
            api_url: Optional custom API URL (overrides config)
            max_retries: Maximum number of retry attempts for retryable errors
            retry_delay: Base delay between retries in seconds (uses exponential backoff)
            timeout: Request timeout in seconds
            retry_status_codes: HTTP status codes to retry (defaults to [429, 500, 502, 503, 504])
            silent: Whether to suppress log messages
        """
        self.api_token = api_token
        self.api_url = api_url or API_URL
        self.headers = {**DEFAULT_HEADERS, "X-RFToken": api_token}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.silent = silent
        
        # Default to common retryable status codes if none specified
        self.retry_status_codes = retry_status_codes or [429, 500, 502, 503, 504]
        
        if not self.silent:
            logger.debug("EnhancedApiClient initialized with URL: %s", self.api_url)
    
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
        result = payload.copy()
        
        # Apply DEFAULT_API_OPTIONS if options not present
        if "options" not in result:
            result["options"] = DEFAULT_API_OPTIONS.copy()
            
        # Override debug flag if specified
        if debug:
            if "options" not in result:
                result["options"] = {}
            result["options"]["debug"] = True
            
        return result
    
    def _handle_http_error(self, error: requests.exceptions.HTTPError) -> None:
        """
        Handle HTTP errors by raising appropriate typed exceptions.
        
        Args:
            error: The HTTP error from requests
            
        Raises:
            ApiAuthenticationError: 401 errors
            ApiAccessDeniedError: 403 errors
            ApiRateLimitError: 429 errors
            ApiServerError: 5xx errors
            ApiClientError: Other 4xx errors
        """
        response = error.response
        status_code = response.status_code
        
        try:
            error_data = response.json()
            error_msg = error_data.get("message", str(error))
        except (ValueError, KeyError):
            error_data = {}
            error_msg = str(error)
        
        # Extract retry-after header for rate limiting
        retry_after = None
        if status_code == 429 and "Retry-After" in response.headers:
            try:
                retry_after = int(response.headers["Retry-After"])
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
    
    def send_data(
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
        payload = self.add_default_options(payload, debug)
        
        # For readable logging, show count of IOCs
        ioc_count = len(payload.get("data", []))
        if not self.silent:
            logger.info("Sending %d detection(s) to %s (debug=%s)", 
                       ioc_count, self.api_url, payload.get("options", {}).get("debug", False))
        
        # Initialize retry counter and track attempts
        attempts = 0
        last_error = None
        
        while attempts <= self.max_retries:
            try:
                # Only log retry attempts after the first attempt
                if attempts > 0 and not self.silent:
                    logger.info("Retry attempt %d of %d", attempts, self.max_retries)
                
                response = requests.post(
                    self.api_url, 
                    headers=self.headers, 
                    json=payload, 
                    timeout=self.timeout
                )
                # Raise HTTPError for bad status codes
                response.raise_for_status()
                
                # Attempt to parse response as JSON
                try:
                    result = response.json()
                    
                    # Log success with summary if available
                    if not self.silent:
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
                    if not self.silent:
                        logger.warning("Could not parse API response as JSON: %s", str(e))
                    # Return empty dict if we can't parse the response
                    return {}
                    
            except requests.exceptions.HTTPError as e:
                last_error = e
                status_code = e.response.status_code
                
                # Check if we should retry based on status code
                if retry and status_code in self.retry_status_codes and attempts < self.max_retries:
                    # For rate limit errors, use the Retry-After header if available
                    if status_code == 429 and "Retry-After" in e.response.headers:
                        try:
                            delay = int(e.response.headers["Retry-After"])
                            logger.info("Rate limited. Waiting %d seconds before retry.", delay)
                            time.sleep(delay)
                        except (ValueError, TypeError):
                            # If Retry-After header is invalid, use exponential backoff
                            delay = self.retry_delay * (2 ** attempts)
                            logger.info("Rate limited. Using exponential backoff: waiting %.1f seconds", delay)
                            time.sleep(delay)
                    else:
                        # Use exponential backoff for other retryable errors
                        delay = self.retry_delay * (2 ** attempts)
                        logger.info("Retryable error (status=%d). Waiting %.1f seconds", status_code, delay)
                        time.sleep(delay)
                    
                    attempts += 1
                    continue
                else:
                    # If not retrying or max retries reached, handle the error
                    self._handle_http_error(e)
                    
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning("Request timed out after %.1f seconds", self.timeout)
                
                if retry and attempts < self.max_retries:
                    delay = self.retry_delay * (2 ** attempts)
                    logger.info("Retrying after timeout. Waiting %.1f seconds", delay)
                    time.sleep(delay)
                    attempts += 1
                    continue
                else:
                    raise ApiTimeoutError(f"Request timed out after {self.timeout} seconds")
                    
            except requests.exceptions.ConnectionError as e:
                last_error = e
                logger.warning("Connection error: %s", str(e))
                
                if retry and attempts < self.max_retries:
                    delay = self.retry_delay * (2 ** attempts)
                    logger.info("Retrying after connection error. Waiting %.1f seconds", delay)
                    time.sleep(delay)
                    attempts += 1
                    continue
                else:
                    raise ApiConnectionError(f"Connection failed: {str(e)}")
                    
            except Exception as e:
                # Unexpected errors won't be retried
                logger.error("Unexpected error: %s", str(e), exc_info=True)
                raise ApiError(f"Unexpected error: {str(e)}")
        
        # If we've exhausted retries, re-raise the last error
        if isinstance(last_error, requests.exceptions.HTTPError):
            self._handle_http_error(last_error)
        elif isinstance(last_error, requests.exceptions.Timeout):
            raise ApiTimeoutError(f"Request timed out after {self.max_retries} retries")
        elif isinstance(last_error, requests.exceptions.ConnectionError):
            raise ApiConnectionError(f"Connection failed after {self.max_retries} retries: {str(last_error)}")
        else:
            raise ApiError(f"Failed after {self.max_retries} retries: {str(last_error) if last_error else 'Unknown error'}")
    
    def batch_send(
        self, 
        payloads: Sequence[Mapping[str, Any]], 
        debug: bool = False,
        continue_on_error: bool = False
    ) -> list[dict[str, Any]]:
        """
        Send multiple payloads to the API in sequence.
        
        Args:
            payloads: List of payload dictionaries to send
            debug: Whether to enable debug mode for all payloads
            continue_on_error: Whether to continue sending on error
            
        Returns:
            List of API responses or error dictionaries
            
        Raises:
            Various API errors if continue_on_error is False
        """
        results = []
        
        for i, payload in enumerate(payloads):
            try:
                if not self.silent:
                    logger.info("Processing batch payload %d of %d", i + 1, len(payloads))
                
                response = self.send_data(payload, debug=debug)
                results.append(response)
                
            except ApiError as e:
                if not self.silent:
                    logger.error("Error processing payload %d: %s", i + 1, str(e))
                
                if continue_on_error:
                    # Add error information to results
                    results.append({
                        "error": str(e),
                        "status_code": getattr(e, "status_code", None),
                        "payload_index": i
                    })
                else:
                    # Re-raise the exception
                    raise
                    
        return results
        
