#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the error analyzer module.
"""

import json
from unittest.mock import MagicMock

import pytest

from sendDetections.error_analyzer import ErrorAnalyzer, ErrorCollection
from sendDetections.errors import (
    ApiAuthenticationError, ApiRateLimitError, PayloadValidationError
)


class TestErrorAnalyzer:
    """Tests for the ErrorAnalyzer class."""
    
    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = ErrorAnalyzer()
        # Check for compiled patterns
        assert len(analyzer.compiled_patterns) > 0
    
    def test_analyze_error_dict(self):
        """Test analyzing error from dictionary."""
        analyzer = ErrorAnalyzer()
        
        # Test with a dictionary error
        error_dict = {
            "type": "RateLimit",
            "message": "API rate limit exceeded, please try again later."
        }
        
        result = analyzer.analyze_error(error_dict)
        
        assert result["type"] == "RateLimit"
        assert "message" in result
        assert "suggestion" in result
        assert "timestamp" in result
    
    def test_analyze_error_exception(self):
        """Test analyzing error from exception."""
        analyzer = ErrorAnalyzer()
        
        # Test with an exception
        error = ApiRateLimitError("Rate limit exceeded", 429)
        
        result = analyzer.analyze_error(error)
        
        assert result["type"] == "RateLimit"
        # Check for generic keywords in suggestion instead of exact text
        assert "request" in result["suggestion"].lower() or "rate" in result["suggestion"].lower()
        assert "message" in result
    
    def test_analyze_batch(self):
        """Test analyzing a batch of errors."""
        analyzer = ErrorAnalyzer()
        
        # Create a mixed set of errors
        errors = [
            ApiAuthenticationError("Invalid token", 401),
            ApiRateLimitError("Rate limit exceeded", 429),
            ApiRateLimitError("Too many requests", 429),
            PayloadValidationError("Invalid field: data[0].ioc.type")
        ]
        
        result = analyzer.analyze_batch(errors)
        
        # Check result structure
        assert "count" in result
        assert "error_types" in result
        assert "suggestions" in result
        assert "errors" in result
        assert "summary" in result
        
        # Check counts
        assert result["count"] == 4
        assert result["error_types"]["RateLimit"] == 2
        assert result["error_types"]["Authentication"] == 1
        assert result["error_types"]["Validation"] == 1
        
        # Check for patterns detection
        assert result["has_patterns"] is True
        assert "RateLimit" in result["primary_error_type"]
    
    def test_analyze_empty_batch(self):
        """Test analyzing an empty batch."""
        analyzer = ErrorAnalyzer()
        
        result = analyzer.analyze_batch([])
        
        assert result["count"] == 0
        assert "No errors to analyze" in result["message"]
    
    def test_suggest_fixes(self):
        """Test generating fix suggestions."""
        analyzer = ErrorAnalyzer()
        
        # Create an analysis result
        analysis = {
            "errors": [
                {"type": "RateLimit", "message": "Too many requests"},
                {"type": "RateLimit", "message": "Rate limit exceeded"}
            ],
            "error_types": {
                "RateLimit": 2
            }
        }
        
        suggestions = analyzer.suggest_fixes(analysis)
        
        # Check suggestions
        assert len(suggestions) > 0
        assert "issue" in suggestions[0]
        assert "suggestion" in suggestions[0]
        assert "implementation" in suggestions[0]
        assert "Rate" in suggestions[0]["issue"]
    
    def test_generate_report(self):
        """Test generating a text report."""
        analyzer = ErrorAnalyzer()
        
        # Create a mock analysis
        analysis = {
            "count": 3,
            "error_types": {
                "RateLimit": 2,
                "Validation": 1
            },
            "errors": [
                {"type": "RateLimit", "message": "Too many requests"},
                {"type": "RateLimit", "message": "Rate limit exceeded"},
                {"type": "Validation", "message": "Invalid field"}
            ]
        }
        
        report = analyzer.generate_report(analysis)
        
        # Check report structure
        assert "Error Analysis Report" in report
        assert "Error distribution" in report
        assert "Suggested fixes" in report
        assert "RateLimit: 2" in report


class TestErrorCollection:
    """Tests for the ErrorCollection class."""
    
    def test_initialization(self):
        """Test collection initialization."""
        collection = ErrorCollection()
        assert collection.errors == []
        assert collection.error_count == 0
        assert collection.error_types == {}
    
    def test_add_error_exception(self):
        """Test adding an exception to the collection."""
        collection = ErrorCollection()
        
        # Add an exception
        error = ApiRateLimitError("Rate limit exceeded", 429)
        collection.add_error(error)
        
        # Check error was added
        assert collection.error_count == 1
        assert collection.error_types["ApiRateLimitError"] == 1
        assert len(collection.errors) == 1
        assert collection.errors[0]["type"] == "ApiRateLimitError"
        assert "status_code" in collection.errors[0]
    
    def test_add_error_with_context(self):
        """Test adding an error with context."""
        collection = ErrorCollection()
        
        # Add an error with context
        context = {"file": "test.json", "line": 42}
        collection.add_error("Test error", context)
        
        # Check error and context were added
        assert collection.error_count == 1
        assert collection.errors[0]["file"] == "test.json"
        assert collection.errors[0]["line"] == 42
    
    def test_get_errors_filtered(self):
        """Test getting errors filtered by type."""
        collection = ErrorCollection()
        
        # Add different types of errors
        collection.add_error(ApiRateLimitError("Rate limit exceeded", 429))
        collection.add_error(ApiAuthenticationError("Invalid token", 401))
        collection.add_error(ApiRateLimitError("Too many requests", 429))
        
        # Get all errors
        all_errors = collection.get_errors()
        assert len(all_errors) == 3
        
        # Get filtered errors
        rate_errors = collection.get_errors("ApiRateLimitError")
        assert len(rate_errors) == 2
        assert all(e["type"] == "ApiRateLimitError" for e in rate_errors)
    
    def test_get_summary(self):
        """Test getting error summary."""
        collection = ErrorCollection()
        
        # Add different types of errors
        collection.add_error(ApiRateLimitError("Rate limit exceeded", 429))
        collection.add_error(ApiAuthenticationError("Invalid token", 401))
        collection.add_error(ApiRateLimitError("Too many requests", 429))
        
        summary = collection.get_summary()
        
        # Check summary structure
        assert summary["total_errors"] == 3
        assert "error_types" in summary
        assert summary["error_types"]["ApiRateLimitError"] == 2
        assert summary["most_common_type"] == "ApiRateLimitError"
        assert summary["has_api_errors"] is True
    
    def test_analyze(self):
        """Test analyzing collected errors."""
        collection = ErrorCollection()
        
        # Add errors
        collection.add_error(ApiRateLimitError("Rate limit exceeded", 429))
        collection.add_error(ApiAuthenticationError("Invalid token", 401))
        
        result = collection.analyze()
        
        # Check analysis result
        assert "analysis" in result
        assert "suggestions" in result
        assert "report" in result
        assert len(result["suggestions"]) > 0
        
    def test_to_json(self):
        """Test converting errors to JSON."""
        collection = ErrorCollection()
        
        # Add an error
        collection.add_error(ApiRateLimitError("Rate limit exceeded", 429))
        
        json_str = collection.to_json()
        
        # Parse JSON and check structure
        data = json.loads(json_str)
        assert "total" in data
        assert "types" in data
        assert "errors" in data
        assert "summary" in data
        assert data["total"] == 1