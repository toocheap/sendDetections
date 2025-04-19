#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Error definitions for sendDetections package.
Custom exception classes for better error handling and reporting.
Uses Python 3.10+ type annotations.
"""

from pathlib import Path
from typing import Any, Optional, Dict, List


class SendDetectionsError(Exception):
    """Base exception class for all sendDetections errors."""
    
    def __init__(self, message: str, *args, **kwargs):
        self.message = message
        super().__init__(message, *args, **kwargs)


class ApiError(SendDetectionsError):
    """Exception for API-related errors."""
    
    def __init__(self, message: str, status_code: int = 0,
                 response_data: Optional[Dict[str, Any]] = None, *args, **kwargs):
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(message, *args, **kwargs)


class ApiAuthenticationError(ApiError):
    """Exception for API authentication failures (401)."""
    pass


class ApiAccessDeniedError(ApiError):
    """Exception for API authorization failures (403)."""
    pass


class ApiRateLimitError(ApiError):
    """Exception for API rate limit errors (429)."""
    
    def __init__(self, message: str, status_code: int = 429,
                 response_data: Optional[Dict[str, Any]] = None,
                 retry_after: Optional[int] = None, *args, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, status_code, response_data, *args, **kwargs)


class ApiServerError(ApiError):
    """Exception for API server errors (5xx)."""
    pass


class ApiClientError(ApiError):
    """Exception for API client errors (4xx)."""
    pass


class ApiConnectionError(ApiError):
    """Exception for connection-related errors."""
    
    def __init__(self, message: str, *args, **kwargs):
        super().__init__(message, 0, None, *args, **kwargs)


class ApiTimeoutError(ApiError):
    """Exception for request timeout errors."""
    
    def __init__(self, message: str, *args, **kwargs):
        super().__init__(message, 0, None, *args, **kwargs)


class PayloadValidationError(SendDetectionsError):
    """Exception for payload validation errors."""
    
    def __init__(self, message: str, field_errors: Optional[List[Dict[str, str]]] = None, 
                 original_data: Optional[Dict[str, Any]] = None, *args, **kwargs):
        self.field_errors = field_errors or []
        self.original_data = original_data
        super().__init__(message, *args, **kwargs)
        
    def get_suggestions(self) -> List[str]:
        """
        Get suggestions for fixing the validation errors.
        
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        # Common error patterns and their suggestions
        if "IoC type must be one of" in self.message:
            suggestions.append("Valid IoC types are: ip, domain, hash, vulnerability, url")
            suggestions.append("Example: {'type': 'ip', 'value': '192.168.1.1'}")
            
        elif "IoC value cannot be empty" in self.message:
            suggestions.append("Provide a non-empty value for the IoC")
            suggestions.append("Example: {'type': 'ip', 'value': '192.168.1.1'}")
            
        elif "sub_type is required when type is 'detection_rule'" in self.message:
            suggestions.append("Add 'sub_type' field to the detection object")
            suggestions.append("Valid sub_types are: sigma, yara, snort")
            suggestions.append("Example: {'type': 'detection_rule', 'sub_type': 'sigma', 'id': 'doc:123'}")
            
        elif "Timestamp must be in ISO 8601 format" in self.message:
            suggestions.append("Use ISO 8601 format: YYYY-MM-DDThh:mm:ssZ")
            suggestions.append("Example: '2023-01-01T12:00:00Z'")
            
        elif "data" in self.message and "empty" in self.message:
            suggestions.append("The 'data' field must contain at least one detection entry")
            suggestions.append("Example: {'data': [{'ioc': {...}, 'detection': {...}}]}")
            
        # Add more patterns as needed
            
        # Generic suggestions if none matched
        if not suggestions:
            suggestions.append("Check the field format and required properties")
            suggestions.append("Refer to the API documentation for field requirements")
            
        return suggestions
        

class CSVConversionError(SendDetectionsError):
    """Exception for CSV conversion errors."""
    
    def __init__(self, message: str, file_path: Optional[str] = None, 
                 row_number: Optional[int] = None, *args, **kwargs):
        self.file_path = file_path
        self.row_number = row_number
        super().__init__(message, *args, **kwargs)
        
    def get_suggestions(self) -> List[str]:
        """
        Get suggestions for fixing CSV conversion errors.
        
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        # Common CSV error patterns and their suggestions
        if "Entity ID" in self.message and "missing" in self.message:
            suggestions.append("Ensure the CSV has an 'Entity ID' column")
            suggestions.append("Format should be: type:value (e.g., ip:192.168.1.1)")
            
        elif "Entity" in self.message and "missing" in self.message:
            suggestions.append("Ensure the CSV has an 'Entity' column")
            suggestions.append("This should contain the actual IoC value")
            
        elif "Detectors" in self.message and "missing" in self.message:
            suggestions.append("Ensure the CSV has a 'Detectors' column")
            suggestions.append("This should contain the detection type/name")
            
        elif "invalid format" in self.message.lower():
            suggestions.append("Check the CSV format - ensure it's properly formatted")
            suggestions.append("Verify delimiter is comma (,) and fields are properly quoted if needed")
            
        # Add row information if available
        if self.row_number is not None:
            suggestions.append(f"Error occurs at row {self.row_number}")
            
        # Generic suggestions if none matched
        if not suggestions:
            suggestions.append("Check the CSV format against the expected schema")
            suggestions.append("See sample files in the sample/ directory for reference")
            
        return suggestions


class ConfigurationError(SendDetectionsError):
    """Exception for configuration-related errors."""
    
    def get_suggestions(self) -> List[str]:
        """
        Get suggestions for fixing configuration errors.
        
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        # Common configuration error patterns
        if "API token" in self.message:
            suggestions.append("Set the RF_API_TOKEN environment variable")
            suggestions.append("Or use the --token/-t command line option")
            suggestions.append("Or create a .env file with RF_API_TOKEN=your_token")
            
        elif "config file" in self.message.lower():
            suggestions.append("Check that the config file exists and has correct permissions")
            suggestions.append("Use --config option to specify an alternate config file")
            suggestions.append("Run 'sendDetections config init' to create a default config file")
            
        # Generic suggestions
        if not suggestions:
            suggestions.append("Check your configuration settings and environment variables")
            suggestions.append("Run with --debug flag for more detailed information")
            
        return suggestions


class FileOperationError(SendDetectionsError):
    """Exception for file operation errors."""
    
    def __init__(self, message: str, file_path: Optional[str] = None, *args, **kwargs):
        self.file_path = file_path
        super().__init__(message, *args, **kwargs)
        
    def get_suggestions(self) -> List[str]:
        """
        Get suggestions for fixing file operation errors.
        
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        # File-related error patterns
        if "permission denied" in self.message.lower():
            suggestions.append("Check file permissions")
            suggestions.append("Ensure you have read/write access to the file")
            
        elif "no such file" in self.message.lower() or "not found" in self.message.lower():
            suggestions.append("Verify the file path is correct")
            suggestions.append("Check that the file exists")
            
        elif "is a directory" in self.message.lower():
            suggestions.append("Expected a file but found a directory")
            suggestions.append("Specify a file path, not a directory")
            
        # Generic suggestions
        if not suggestions:
            suggestions.append("Check the file path and permissions")
            suggestions.append("Ensure the directory exists and is accessible")
            
        return suggestions