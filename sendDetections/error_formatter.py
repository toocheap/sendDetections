#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Error formatting utilities for improved UX when displaying errors.
Provides context-rich, user-friendly error messages and suggestions.
"""

import re
import textwrap
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from sendDetections.errors import (
    SendDetectionsError, ApiError, ApiAuthenticationError,
    ApiRateLimitError, ApiServerError, ApiConnectionError,
    ApiTimeoutError, PayloadValidationError, CSVConversionError,
    ConfigurationError, FileOperationError
)

# Configure logger
logger = logging.getLogger(__name__)

class ErrorFormatter:
    """Format errors into user-friendly messages with context and suggestions."""
    
    # ANSI color codes for terminal output
    COLORS = {
        'reset': '\033[0m',
        'red': '\033[31m',
        'green': '\033[32m',
        'yellow': '\033[33m',
        'blue': '\033[34m',
        'magenta': '\033[35m',
        'cyan': '\033[36m',
        'white': '\033[37m',
        'bold': '\033[1m',
        'underline': '\033[4m',
    }
    
    def __init__(self, use_colors: bool = True, terminal_width: int = 80):
        """
        Initialize the error formatter.
        
        Args:
            use_colors: Whether to use ANSI colors in output
            terminal_width: Terminal width for text wrapping
        """
        self.use_colors = use_colors
        self.terminal_width = terminal_width
    
    def format(self, error: Any) -> str:
        """
        Format an error into a user-friendly message.
        
        Args:
            error: Error object or exception
            
        Returns:
            Formatted error message with context and suggestions
        """
        if isinstance(error, ApiError):
            return self._format_api_error(error)
        elif isinstance(error, PayloadValidationError):
            return self._format_validation_error(error)
        elif isinstance(error, CSVConversionError):
            return self._format_csv_error(error)
        elif isinstance(error, ConfigurationError):
            return self._format_config_error(error)
        elif isinstance(error, FileOperationError):
            return self._format_file_error(error)
        elif isinstance(error, SendDetectionsError):
            return self._format_general_error(error)
        elif isinstance(error, Exception):
            return self._format_exception(error)
        else:
            return self._format_unknown_error(error)
    
    def _apply_color(self, text: str, color: str) -> str:
        """Apply ANSI color if colors are enabled."""
        if not self.use_colors:
            return text
        color_code = self.COLORS.get(color, '')
        if not color_code:
            return text
        return f"{color_code}{text}{self.COLORS['reset']}"
    
    def _wrap_text(self, text: str, indent: int = 0) -> str:
        """Wrap text to terminal width with optional indentation."""
        wrapped = textwrap.fill(
            text,
            width=self.terminal_width - indent,
            initial_indent=' ' * indent,
            subsequent_indent=' ' * indent
        )
        return wrapped
    
    def _format_header(self, error_type: str) -> str:
        """Format the error header."""
        header = f"ERROR: {error_type}"
        return self._apply_color(header, 'bold')
    
    def _format_message(self, message: str) -> str:
        """Format the main error message."""
        wrapped = self._wrap_text(message, indent=2)
        return self._apply_color(wrapped, 'red')
    
    def _format_context(self, context_items: Dict[str, Any]) -> str:
        """Format error context information."""
        if not context_items:
            return ""
            
        lines = [self._apply_color("Context:", 'bold')]
        for key, value in context_items.items():
            if value is not None:
                key_str = self._apply_color(f"{key}:", 'cyan')
                lines.append(f"  {key_str} {value}")
        
        return "\n".join(lines)
    
    def _format_suggestions(self, suggestions: List[str]) -> str:
        """Format error fix suggestions."""
        if not suggestions:
            return ""
            
        lines = [self._apply_color("Suggestions:", 'bold')]
        for i, suggestion in enumerate(suggestions, 1):
            bullet = self._apply_color(f"{i}.", 'green')
            suggestion_text = self._wrap_text(suggestion, indent=5)
            # Add indentation to the bullet point
            suggestion_text = f"  {bullet} {suggestion_text[5:]}"
            lines.append(suggestion_text)
        
        return "\n".join(lines)
    
    def _format_api_error(self, error: ApiError) -> str:
        """Format API errors with specific context and suggestions."""
        # Determine the specific error type
        if isinstance(error, ApiAuthenticationError):
            error_type = "API Authentication Error"
            suggestions = [
                "Check that your API token is correct and not expired",
                "Verify the token has the required permissions",
                "Try regenerating the token in your Recorded Future account"
            ]
        elif isinstance(error, ApiRateLimitError):
            error_type = "API Rate Limit Exceeded"
            retry_msg = f" (retry after {error.retry_after}s)" if error.retry_after else ""
            suggestions = [
                f"Wait before retrying{retry_msg}",
                "Reduce the request frequency with --max-concurrent and --batch-size",
                "Implement exponential backoff or use the batch processing mode"
            ]
        elif isinstance(error, ApiServerError):
            error_type = "API Server Error"
            suggestions = [
                "This is an issue with the Recorded Future API servers",
                "Try again later or contact Recorded Future support",
                "Use the batch processing mode with retries enabled"
            ]
        elif isinstance(error, ApiConnectionError):
            error_type = "API Connection Error"
            suggestions = [
                "Check your network connection",
                "Verify that the API endpoint is correct",
                "Check if your firewall or proxy is blocking the connection"
            ]
        elif isinstance(error, ApiTimeoutError):
            error_type = "API Timeout Error"
            suggestions = [
                "The request took too long to complete",
                "Try using smaller batch sizes",
                "Check your network connection speed"
            ]
        else:
            error_type = "API Error"
            suggestions = [
                "Check the error message for details",
                "Verify your request payload format",
                "Try with the --debug flag for additional information"
            ]
        
        # Build context information
        context = {}
        if error.status_code:
            context["Status code"] = error.status_code
        if error.response_data:
            if 'message' in error.response_data:
                context["API message"] = error.response_data['message']
            if 'documentation_url' in error.response_data:
                context["Documentation"] = error.response_data['documentation_url']
        
        # Construct the formatted message
        parts = [
            self._format_header(error_type),
            self._format_message(error.message),
            self._format_context(context),
            self._format_suggestions(suggestions)
        ]
        
        return "\n\n".join(filter(bool, parts))
    
    def _format_validation_error(self, error: PayloadValidationError) -> str:
        """Format validation errors with field details and suggestions."""
        error_type = "Payload Validation Error"
        
        # Build context information
        context = {}
        if error.field_errors:
            context["Field errors"] = f"{len(error.field_errors)} field(s) with issues"
            # Add specific field errors
            for i, field_error in enumerate(error.field_errors[:3], 1):
                field = field_error.get('field', 'unknown')
                message = field_error.get('message', 'invalid')
                context[f"Field {i}"] = f"{field}: {message}"
            
            # If there are more errors, indicate this
            if len(error.field_errors) > 3:
                context["Note"] = f"{len(error.field_errors) - 3} more field errors"
        
        # Get suggestions from the error object
        suggestions = error.get_suggestions() if hasattr(error, 'get_suggestions') else [
            "Ensure all required fields are present and have the correct format",
            "Check for typos in field names",
            "Verify value types match the API requirements"
        ]
        
        # Construct the formatted message
        parts = [
            self._format_header(error_type),
            self._format_message(error.message),
            self._format_context(context),
            self._format_suggestions(suggestions)
        ]
        
        return "\n\n".join(filter(bool, parts))
    
    def _format_csv_error(self, error: CSVConversionError) -> str:
        """Format CSV conversion errors with file context and suggestions."""
        error_type = "CSV Conversion Error"
        
        # Build context information
        context = {}
        if error.file_path:
            context["File"] = error.file_path
        if error.row_number is not None:
            context["Row"] = error.row_number
        
        # Get suggestions from the error object
        suggestions = error.get_suggestions() if hasattr(error, 'get_suggestions') else [
            "Check the CSV file format and structure",
            "Ensure the CSV headers match the expected schema",
            "Verify the file is properly formatted CSV with UTF-8 encoding"
        ]
        
        # Construct the formatted message
        parts = [
            self._format_header(error_type),
            self._format_message(error.message),
            self._format_context(context),
            self._format_suggestions(suggestions)
        ]
        
        return "\n\n".join(filter(bool, parts))
    
    def _format_config_error(self, error: ConfigurationError) -> str:
        """Format configuration errors with suggestions."""
        error_type = "Configuration Error"
        
        # Get suggestions from the error object
        suggestions = error.get_suggestions() if hasattr(error, 'get_suggestions') else [
            "Check your configuration file syntax",
            "Verify environment variables are set correctly",
            "Use --config to specify an alternate configuration file"
        ]
        
        # Construct the formatted message
        parts = [
            self._format_header(error_type),
            self._format_message(error.message),
            self._format_suggestions(suggestions)
        ]
        
        return "\n\n".join(filter(bool, parts))
    
    def _format_file_error(self, error: FileOperationError) -> str:
        """Format file operation errors with path context and suggestions."""
        error_type = "File Operation Error"
        
        # Build context information
        context = {}
        if error.file_path:
            context["File"] = error.file_path
        
        # Get suggestions from the error object
        suggestions = error.get_suggestions() if hasattr(error, 'get_suggestions') else [
            "Check that the file exists and you have appropriate permissions",
            "Verify the path is correctly specified",
            "Ensure the directory is accessible"
        ]
        
        # Construct the formatted message
        parts = [
            self._format_header(error_type),
            self._format_message(error.message),
            self._format_context(context),
            self._format_suggestions(suggestions)
        ]
        
        return "\n\n".join(filter(bool, parts))
    
    def _format_general_error(self, error: SendDetectionsError) -> str:
        """Format general SendDetections errors."""
        error_type = error.__class__.__name__.replace("Error", " Error")
        
        # Try to get suggestions if the method exists
        suggestions = error.get_suggestions() if hasattr(error, 'get_suggestions') else [
            "Check the error message for details",
            "Try running with the --debug flag for more information",
            "Refer to the documentation for help with this error type"
        ]
        
        # Construct the formatted message
        parts = [
            self._format_header(error_type),
            self._format_message(error.message),
            self._format_suggestions(suggestions)
        ]
        
        return "\n\n".join(filter(bool, parts))
    
    def _format_exception(self, error: Exception) -> str:
        """Format standard Python exceptions."""
        error_type = f"Python {error.__class__.__name__}"
        
        # Construct the formatted message
        parts = [
            self._format_header(error_type),
            self._format_message(str(error)),
            self._format_suggestions([
                "This is an unexpected error in the application",
                "Try running with --debug for more detailed information",
                "Consider reporting this as a bug"
            ])
        ]
        
        return "\n\n".join(filter(bool, parts))
    
    def _format_unknown_error(self, error: Any) -> str:
        """Format unknown error types."""
        # Construct the formatted message
        parts = [
            self._format_header("Unknown Error"),
            self._format_message(str(error)),
            self._format_suggestions([
                "This is an unexpected error of unknown type",
                "Try running with --debug for more detailed information",
                "Consider reporting this as a bug"
            ])
        ]
        
        return "\n\n".join(filter(bool, parts))


# Global instance for easy access
default_formatter = ErrorFormatter()

def format_error(error: Any, use_colors: bool = True) -> str:
    """
    Format an error for user-friendly display.
    
    Args:
        error: Error object or exception
        use_colors: Whether to use colors in the output
        
    Returns:
        Formatted error message
    """
    formatter = ErrorFormatter(use_colors=use_colors)
    return formatter.format(error)


def print_error(error: Any, use_colors: bool = True) -> None:
    """
    Print a formatted error message.
    
    Args:
        error: Error object or exception
        use_colors: Whether to use colors in the output
    """
    formatted = format_error(error, use_colors)
    print(formatted)


def get_error_summary(error: Any) -> Dict[str, Any]:
    """
    Get a structured summary of an error for logging or display.
    
    Args:
        error: Error object or exception
        
    Returns:
        Dictionary with error information
    """
    # Basic error info
    summary = {
        "type": error.__class__.__name__ if isinstance(error, Exception) else type(error).__name__,
        "message": str(error),
    }
    
    # Add API-specific information
    if isinstance(error, ApiError):
        summary.update({
            "status_code": error.status_code,
            "api_data": error.response_data,
        })
        
        # Add retry information for rate limit errors
        if isinstance(error, ApiRateLimitError) and error.retry_after:
            summary["retry_after"] = error.retry_after
    
    # Add validation error details
    elif isinstance(error, PayloadValidationError):
        summary["field_errors"] = error.field_errors
    
    # Add CSV conversion details
    elif isinstance(error, CSVConversionError):
        if error.file_path:
            summary["file"] = error.file_path
        if error.row_number is not None:
            summary["row"] = error.row_number
    
    # Add file error details
    elif isinstance(error, FileOperationError):
        if error.file_path:
            summary["file"] = error.file_path
    
    return summary