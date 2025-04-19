#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API client for Recorded Future Collective Insights Detection API.
"""

import logging
from typing import Any, Dict, Optional, Union, cast

import requests
from pydantic import ValidationError

from sendDetections.config import API_URL, DEFAULT_HEADERS, DEFAULT_API_OPTIONS
from sendDetections.validators import validate_payload, ApiPayload

# Configure logger
logger = logging.getLogger(__name__)

class ApiError(Exception):
    """API-related error with status code and message."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class DetectionApiClient:
    """
    Client for sending data to Recorded Future Collective Insights Detection API.
    """

    def __init__(self, api_token: str, api_url: Optional[str] = None):
        """
        Initialize the API client.
        
        Args:
            api_token: Recorded Future API token
            api_url: Optional custom API URL (overrides config)
        """
        self.api_token = api_token
        self.api_url = api_url or API_URL
        self.headers = {**DEFAULT_HEADERS, "X-RFToken": api_token}
    
    @staticmethod
    def validate_payload(payload: Dict[str, Any]) -> Optional[str]:
        """
        Validate a payload dict. Returns an error message if invalid, else None.
        """
        return validate_payload(payload)

    def add_default_options(self, payload: Dict[str, Any], debug: bool = False) -> Dict[str, Any]:
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

    def send_data(self, payload: Dict[str, Any], debug: bool = False) -> Dict[str, Any]:
        """
        Send data to the API.
        
        Args:
            payload: The data payload to send
            debug: Whether to enable debug mode
            
        Returns:
            API response as a dictionary
            
        Raises:
            ApiError: On API errors (HTTP status codes, connection issues)
            ValidationError: On invalid payload structure
        """
        # Pre-send validation
        if (error := validate_payload(payload)):
            raise ValidationError(error, ApiPayload)

        # Apply default options and debug flag
        payload = self.add_default_options(payload, debug)
        
        try:
            logger.debug(f"Sending request to {self.api_url}")
            response = requests.post(
                self.api_url, 
                headers=self.headers, 
                json=payload, 
                timeout=30
            )
            response.raise_for_status()
            return cast(Dict[str, Any], response.json())
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            try:
                error_data = e.response.json()
                error_msg = error_data.get("message", str(e))
            except Exception:
                error_msg = str(e)
                
            # Map status codes to more descriptive messages
            status_messages = {
                400: f"Bad Request: {error_msg}",
                401: f"Authentication failed: {error_msg}",
                403: f"Access denied: {error_msg}",
                429: f"Too many requests: {error_msg}",
                500: f"Server internal error: {error_msg}"
            }
            
            message = status_messages.get(status_code, f"HTTP Error {status_code}: {error_msg}")
            logger.error(f"API error: {message}")
            raise ApiError(message, status_code)
            
        except requests.exceptions.ConnectionError as e:
            message = f"Cannot connect to API server: {e}"
            logger.error(message)
            raise ApiError(message)
            
        except Exception as e:
            message = f"Unexpected error: {e}"
            logger.error(message)
            raise ApiError(message)