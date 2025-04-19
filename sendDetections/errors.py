#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Custom exception classes for error handling in the sendDetections package.
Provides specific, typed exceptions for different error scenarios.
"""

from typing import Any, Dict, List, Optional


class SendDetectionsError(Exception):
    """Base class for all sendDetections exceptions."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ApiError(SendDetectionsError):
    """Base class for API-related errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response_data: Optional[Dict[str, Any]] = None):
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(message)
        

class ApiAuthenticationError(ApiError):
    """Authentication failure (invalid API key, expired token)."""
    pass


class ApiAccessDeniedError(ApiError):
    """Authorization failure (insufficient permissions)."""
    pass


class ApiRateLimitError(ApiError):
    """API rate limit exceeded."""
    def __init__(self, message: str, status_code: Optional[int] = None,
                 response_data: Optional[Dict[str, Any]] = None,
                 retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(message, status_code, response_data)


class ApiServerError(ApiError):
    """Server-side error (5xx responses)."""
    pass


class ApiClientError(ApiError):
    """Client-side error (4xx responses not covered by specific exceptions)."""
    pass


class ApiConnectionError(ApiError):
    """Network connectivity issues."""
    pass


class ApiTimeoutError(ApiError):
    """Request timeout error."""
    pass


class PayloadValidationError(SendDetectionsError):
    """Error in payload structure or content validation."""
    def __init__(self, message: str, field_errors: Optional[List[Dict[str, Any]]] = None):
        self.field_errors = field_errors or []
        super().__init__(message)


class CSVConversionError(SendDetectionsError):
    """Error during CSV to JSON conversion."""
    def __init__(self, message: str, file_path: Optional[str] = None, 
                 row_number: Optional[int] = None):
        self.file_path = file_path
        self.row_number = row_number
        super().__init__(message)


class ConfigurationError(SendDetectionsError):
    """Error in configuration settings."""
    pass


class FileOperationError(SendDetectionsError):
    """Error during file read/write operations."""
    def __init__(self, message: str, file_path: Optional[str] = None):
        self.file_path = file_path
        super().__init__(message)