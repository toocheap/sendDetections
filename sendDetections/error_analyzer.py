#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Error analysis utilities for diagnosing API and processing errors.
Provides tools for grouping, categorizing, and suggesting fixes for common errors.
"""

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from sendDetections.errors import (
    SendDetectionsError, ApiError, ApiAuthenticationError,
    ApiRateLimitError, ApiServerError, ApiConnectionError,
    ApiTimeoutError, PayloadValidationError, CSVConversionError
)

# Configure logger
logger = logging.getLogger(__name__)


class ErrorAnalyzer:
    """
    Analyze errors from batch processing to identify patterns and suggest solutions.
    """
    
    # Common error patterns and suggested solutions
    ERROR_PATTERNS = [
        {
            "pattern": r"rate limit|too many requests|429|too frequent",
            "type": "RateLimit",
            "message": "API rate limit exceeded",
            "suggestion": "Reduce request frequency or implement exponential backoff"
        },
        {
            "pattern": r"authentication failed|invalid token|unauthorized|401",
            "type": "Authentication",
            "message": "API authentication failed",
            "suggestion": "Check API token validity and permissions"
        },
        {
            "pattern": r"access denied|forbidden|403",
            "type": "Authorization",
            "message": "Authorization error",
            "suggestion": "Verify API token has necessary permissions"
        },
        {
            "pattern": r"timeout|timed out|too slow",
            "type": "Timeout",
            "message": "Request timeout",
            "suggestion": "Increase timeout settings or optimize payload size"
        },
        {
            "pattern": r"server error|5\d\d|internal error",
            "type": "ServerError",
            "message": "Server-side error",
            "suggestion": "Retry with exponential backoff or contact API provider"
        },
        {
            "pattern": r"connection|failed to connect|network|unreachable",
            "type": "Connection",
            "message": "Connection error",
            "suggestion": "Check network connectivity and DNS settings"
        },
        {
            "pattern": r"validation|invalid|missing required|schema",
            "type": "Validation",
            "message": "Payload validation error",
            "suggestion": "Check payload format against API requirements"
        },
        {
            "pattern": r"csv|conversion|parsing|encoding|delimiter",
            "type": "CSVConversion",
            "message": "CSV conversion error",
            "suggestion": "Verify CSV format, encoding, and required columns"
        }
    ]
    
    def __init__(self):
        """Initialize the error analyzer."""
        # Compile regex patterns for faster matching
        self.compiled_patterns = [
            (re.compile(p["pattern"], re.IGNORECASE), p)
            for p in self.ERROR_PATTERNS
        ]
    
    def analyze_error(self, error: Any) -> Dict[str, Any]:
        """
        Analyze a single error and return structured information.
        
        Args:
            error: Error object or dictionary
            
        Returns:
            Structured error information with suggestions
        """
        # Extract error information based on type
        if isinstance(error, dict):
            error_type = error.get("type", "UnknownError")
            error_message = error.get("message", str(error))
            error_details = error
        elif isinstance(error, ApiError):
            error_type = error.__class__.__name__
            error_message = error.message
            error_details = {
                "message": error.message,
                "status_code": getattr(error, "status_code", None)
            }
        elif isinstance(error, Exception):
            error_type = error.__class__.__name__
            error_message = str(error)
            error_details = {"message": error_message}
        else:
            error_type = "UnknownError"
            error_message = str(error)
            error_details = {"message": error_message}
        
        # Match against known patterns for suggestions
        suggestion = "No specific suggestion available"
        for pattern, info in self.compiled_patterns:
            if pattern.search(error_message.lower()):
                error_type = info["type"]
                suggestion = info["suggestion"]
                break
        
        # Build structured error analysis
        return {
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": error_message,
            "details": error_details,
            "suggestion": suggestion
        }
    
    def analyze_batch(self, errors: List[Any]) -> Dict[str, Any]:
        """
        Analyze a batch of errors to identify patterns and common issues.
        
        Args:
            errors: List of error objects or dictionaries
            
        Returns:
            Analysis report with error counts, patterns, and suggestions
        """
        if not errors:
            return {
                "count": 0,
                "message": "No errors to analyze",
                "errors": [],
                "summary": {}
            }
        
        # Analyze each error
        analyzed_errors = [self.analyze_error(error) for error in errors]
        
        # Count error types
        error_types = Counter(error["type"] for error in analyzed_errors)
        
        # Group by suggestion
        suggestions = defaultdict(list)
        for error in analyzed_errors:
            suggestions[error["suggestion"]].append(error["type"])
            
        suggestion_counts = {
            suggestion: len(types)
            for suggestion, types in suggestions.items()
        }
        
        # Determine if there are patterns in the errors
        has_patterns = len(error_types) < len(analyzed_errors)
        primary_error_type = error_types.most_common(1)[0][0] if error_types else "Unknown"
        
        # Generate summary message
        if len(error_types) == 1:
            summary_message = f"All errors are of type {primary_error_type}"
        else:
            summary_message = f"Multiple error types detected, most common: {primary_error_type} ({error_types[primary_error_type]} occurrences)"
        
        # Compile report
        return {
            "count": len(analyzed_errors),
            "message": summary_message,
            "has_patterns": has_patterns,
            "primary_error_type": primary_error_type,
            "error_types": dict(error_types),
            "suggestions": suggestion_counts,
            "errors": analyzed_errors,
            "summary": {
                "error_count": len(analyzed_errors),
                "unique_error_types": len(error_types),
                "primary_suggestion": max(suggestion_counts.items(), key=lambda x: x[1])[0] if suggestion_counts else "No suggestion"
            }
        }
    
    def suggest_fixes(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate specific fix suggestions based on error analysis.
        
        Args:
            analysis: Error analysis from analyze_batch()
            
        Returns:
            List of specific fix suggestions
        """
        if not analysis.get("errors"):
            return []
        
        suggestions = []
        error_types = analysis.get("error_types", {})
        
        # Rate limit errors
        if "RateLimit" in error_types:
            suggestions.append({
                "issue": "Rate limiting",
                "suggestion": "Reduce request frequency or implement exponential backoff",
                "implementation": "Use --max-concurrent=3 and --batch-size=50 to reduce API load"
            })
        
        # Authentication errors
        if "Authentication" in error_types:
            suggestions.append({
                "issue": "Authentication failure",
                "suggestion": "Verify API token",
                "implementation": "Check that your API token is valid and not expired"
            })
        
        # Validation errors
        if "Validation" in error_types:
            field_errors = self._extract_validation_fields(analysis.get("errors", []))
            if field_errors:
                field_list = ", ".join(field_errors)
                suggestions.append({
                    "issue": "Payload validation errors",
                    "suggestion": f"Fix problems in these fields: {field_list}",
                    "implementation": "Ensure all required fields are present and properly formatted"
                })
            else:
                suggestions.append({
                    "issue": "Payload validation errors",
                    "suggestion": "Check payload structure against API requirements",
                    "implementation": "Verify your data matches the expected format"
                })
        
        # Connection errors
        if "Connection" in error_types:
            suggestions.append({
                "issue": "Network connectivity issues",
                "suggestion": "Check network connection and API endpoint",
                "implementation": "Verify internet connection and DNS resolution"
            })
        
        # Timeout errors
        if "Timeout" in error_types:
            suggestions.append({
                "issue": "Request timeouts",
                "suggestion": "Increase timeout or reduce payload size",
                "implementation": "Use smaller batch sizes or increase timeout settings"
            })
        
        # CSV conversion errors
        if "CSVConversion" in error_types:
            suggestions.append({
                "issue": "CSV parsing problems",
                "suggestion": "Check CSV format and required columns",
                "implementation": "Verify CSV contains all required fields with proper data types"
            })
        
        # Add generic suggestion if none found
        if not suggestions:
            suggestions.append({
                "issue": "General errors",
                "suggestion": "Review error details and retry with modified parameters",
                "implementation": "Check logs for specific error messages"
            })
            
        return suggestions
    
    def _extract_validation_fields(self, errors: List[Dict[str, Any]]) -> Set[str]:
        """
        Extract field names from validation errors.
        
        Args:
            errors: List of analyzed errors
            
        Returns:
            Set of field names that have validation errors
        """
        fields = set()
        for error in errors:
            if error.get("type") == "Validation":
                message = error.get("message", "")
                
                # Extract validation paths like 'data[0].ioc.type'
                field_matches = re.findall(r"['\"]([\w\[\].]+)['\"]", message)
                fields.update(field_matches)
                
                # Look for specific mentions of fields
                field_words = re.findall(r"field ['\"]?([\w_]+)['\"]?", message)
                fields.update(field_words)
                
        return fields
    
    def generate_report(self, analysis: Dict[str, Any]) -> str:
        """
        Generate a human-readable report from error analysis.
        
        Args:
            analysis: Error analysis from analyze_batch()
            
        Returns:
            Formatted text report
        """
        if not analysis.get("errors"):
            return "No errors to analyze"
        
        error_count = analysis.get("count", 0)
        error_types = analysis.get("error_types", {})
        suggestions = self.suggest_fixes(analysis)
        
        report = [
            "=== Error Analysis Report ===",
            f"Total errors: {error_count}",
            f"Error types: {len(error_types)}",
            "",
            "Error distribution:",
        ]
        
        for error_type, count in error_types.items():
            report.append(f"  - {error_type}: {count} ({count/error_count*100:.1f}%)")
        
        report.append("")
        report.append("Suggested fixes:")
        
        for i, suggestion in enumerate(suggestions, 1):
            report.append(f"  {i}. {suggestion['issue']}")
            report.append(f"     Suggestion: {suggestion['suggestion']}")
            report.append(f"     Implementation: {suggestion['implementation']}")
            
        return "\n".join(report)


class ErrorCollection:
    """
    Collect and track errors during batch processing.
    """
    
    def __init__(self):
        """Initialize the error collection."""
        self.errors: List[Dict[str, Any]] = []
        self.error_count = 0
        self.error_types: Dict[str, int] = {}
        
    def add_error(
        self, 
        error: Any, 
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an error to the collection with context.
        
        Args:
            error: The error object or message
            context: Additional context about when/where the error occurred
        """
        # Extract error information
        if isinstance(error, dict):
            error_type = error.get("type", "UnknownError")
            error_message = error.get("message", str(error))
        elif isinstance(error, Exception):
            error_type = error.__class__.__name__
            error_message = str(error)
        else:
            error_type = "UnknownError"
            error_message = str(error)
        
        # Update error type counts
        if error_type not in self.error_types:
            self.error_types[error_type] = 0
        self.error_types[error_type] += 1
        
        # Build error entry
        entry = {
            "id": self.error_count + 1,
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": error_message
        }
        
        # Add context if provided
        if context:
            entry.update(context)
            
        # Add status code for API errors
        if isinstance(error, ApiError) and hasattr(error, "status_code"):
            entry["status_code"] = error.status_code
            
        # Add exception information
        if isinstance(error, Exception):
            entry["exception"] = error.__class__.__name__
            
        self.errors.append(entry)
        self.error_count += 1
        
    def get_errors(self, error_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get errors, optionally filtered by type.
        
        Args:
            error_type: Optional error type to filter by
            
        Returns:
            List of matching errors
        """
        if error_type:
            return [e for e in self.errors if e.get("type") == error_type]
        return self.errors
        
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of collected errors.
        
        Returns:
            Summary of error information
        """
        return {
            "total_errors": self.error_count,
            "error_types": self.error_types,
            "most_common_type": max(self.error_types.items(), key=lambda x: x[1])[0] if self.error_types else None,
            "has_api_errors": any(e.get("status_code") is not None for e in self.errors),
            "has_validation_errors": "ValidationError" in self.error_types or "PayloadValidationError" in self.error_types
        }
        
    def analyze(self) -> Dict[str, Any]:
        """
        Analyze all collected errors.
        
        Returns:
            Analysis of error patterns
        """
        analyzer = ErrorAnalyzer()
        analysis = analyzer.analyze_batch(self.errors)
        suggestions = analyzer.suggest_fixes(analysis)
        
        return {
            "analysis": analysis,
            "suggestions": suggestions,
            "report": analyzer.generate_report(analysis)
        }
        
    def to_json(self) -> str:
        """
        Convert errors to JSON format.
        
        Returns:
            JSON string of all errors
        """
        data = {
            "total": self.error_count,
            "types": self.error_types,
            "errors": self.errors,
            "summary": self.get_summary()
        }
        return json.dumps(data, indent=2)