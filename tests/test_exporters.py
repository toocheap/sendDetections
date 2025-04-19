#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the exporters module.
"""

import csv
import json
import os
import tempfile
from pathlib import Path

import pytest

from sendDetections.exporters import ResultExporter


class TestResultExporter:
    """Tests for the ResultExporter class."""
    
    @pytest.fixture
    def sample_results(self):
        """Sample processing results for testing."""
        return [
            {
                "summary": {
                    "submitted": 10,
                    "processed": 8,
                    "dropped": 2
                },
                "performance": {
                    "time": {
                        "total_seconds": 1.5,
                        "avg_call_time": 0.15
                    },
                    "throughput": {
                        "entities_processed": 8,
                        "entities_per_second": 5.33
                    }
                }
            },
            {
                "summary": {
                    "submitted": 5,
                    "processed": 5,
                    "dropped": 0
                },
                "performance": {
                    "time": {
                        "total_seconds": 0.8,
                        "avg_call_time": 0.16
                    },
                    "throughput": {
                        "entities_processed": 5,
                        "entities_per_second": 6.25
                    }
                }
            }
        ]
    
    @pytest.fixture
    def sample_errors(self):
        """Sample errors for testing."""
        return [
            {
                "type": "ValidationError",
                "message": "Invalid field: data[0].ioc.type",
                "file": "test1.json"
            },
            {
                "type": "ApiError",
                "message": "Rate limit exceeded",
                "status_code": 429
            }
        ]
    
    def test_initialization(self):
        """Test exporter initialization."""
        # With default export directory
        exporter = ResultExporter()
        assert exporter.export_dir == Path.cwd()
        
        # With custom export directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            exporter = ResultExporter(export_dir=tmp_path)
            assert exporter.export_dir == tmp_path
    
    def test_export_json(self, sample_results):
        """Test exporting results to JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            exporter = ResultExporter(export_dir=tmp_path)
            
            # Export with auto-generated filename
            data = {"results": sample_results}
            json_path = exporter.export_json(data)
            
            # Verify file was created
            assert json_path.exists()
            
            # Verify content
            with open(json_path) as f:
                exported_data = json.load(f)
                assert exported_data == data
                
            # Export with specific filename
            custom_file = "custom_results.json"
            json_path = exporter.export_json(data, filename=custom_file)
            
            # Verify correct filename was used
            assert json_path.name == custom_file
    
    def test_export_summary_csv(self, sample_results):
        """Test exporting summary to CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            exporter = ResultExporter(export_dir=tmp_path)
            
            # Export with auto-generated filename
            csv_path = exporter.export_summary_csv(sample_results)
            
            # Verify file was created
            assert csv_path.exists()
            
            # Verify CSV content has correct headers and row count
            with open(csv_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                
                # Should have one row per result
                assert len(rows) == len(sample_results)
                
                # Check expected fields are present
                expected_fields = ['batch_id', 'submitted', 'processed', 'dropped']
                for field in expected_fields:
                    assert field in rows[0]
    
    def test_export_errors_csv(self, sample_errors):
        """Test exporting errors to CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            exporter = ResultExporter(export_dir=tmp_path)
            
            # Export with auto-generated filename
            errors_path = exporter.export_errors_csv(sample_errors)
            
            # Verify file was created
            assert errors_path.exists()
            
            # Verify CSV content has correct headers and row count
            with open(errors_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                
                # Should have one row per error
                assert len(rows) == len(sample_errors)
                
                # Check expected fields are present
                assert 'error_type' in rows[0]
                assert 'message' in rows[0]
                
                # Check specific error info is present
                assert rows[0]['error_type'] == sample_errors[0]['type']
                assert rows[1]['error_type'] == sample_errors[1]['type']
    
    def test_generate_report(self, sample_results, sample_errors):
        """Test generating HTML report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            exporter = ResultExporter(export_dir=tmp_path)
            
            # Generate report with auto-generated filename
            report_path = exporter.generate_report(sample_results, sample_errors)
            
            # Verify file was created
            assert report_path.exists()
            
            # Verify it's an HTML file with expected content
            with open(report_path) as f:
                content = f.read()
                assert "<!DOCTYPE html>" in content
                assert "Batch Processing Report" in content
                assert "Summary" in content
                assert "Errors" in content
                
                # Verify results are included
                assert "15" in content  # Total submitted (10+5)
                assert "13" in content  # Total processed (8+5)
                
                # Verify error info is included
                assert "ValidationError" in content
                assert "ApiError" in content
    
    def test_export_all(self, sample_results, sample_errors):
        """Test exporting all formats at once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            exporter = ResultExporter(export_dir=tmp_path)
            
            # Export all formats
            base_filename = "test_export"
            exports = exporter.export_all(
                sample_results,
                sample_errors,
                base_filename=base_filename
            )
            
            # Verify all expected file types were created
            assert 'json' in exports
            assert 'csv_summary' in exports
            assert 'csv_errors' in exports
            assert 'html_report' in exports
            
            # Verify all files exist
            for file_path in exports.values():
                assert file_path.exists()
                
            # Verify base filename was used
            assert base_filename in exports['json'].name