#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the enhanced batch processor functionality.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from sendDetections.batch_processor import BatchProcessor
from sendDetections.performance import PerformanceMetrics
from sendDetections.errors import ApiError, CSVConversionError


class TestBatchProcessor:
    """Tests for the enhanced BatchProcessor class."""
    
    def test_initialization(self):
        """Test batch processor initialization with various parameters."""
        # Test with defaults
        processor = BatchProcessor(api_token="test_token")
        assert processor.api_token == "test_token"
        assert processor.max_concurrent == 5
        assert processor.batch_size == 100
        assert processor.max_retries == 3
        assert processor.show_progress is True
        assert isinstance(processor.metrics, PerformanceMetrics)
        
        # Test with custom values
        processor = BatchProcessor(
            api_token="test_token",
            api_url="https://custom-api.example.com",
            max_concurrent=10,
            batch_size=50,
            max_retries=2,
            show_progress=False
        )
        assert processor.api_token == "test_token"
        assert processor.api_url == "https://custom-api.example.com"
        assert processor.max_concurrent == 10
        assert processor.batch_size == 50
        assert processor.max_retries == 2
        assert processor.show_progress is False


@pytest.mark.asyncio
async def test_process_files_with_metrics():
    """Test processing files with performance metrics."""
    # Create test data
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = Path(tmpdirname)
        
        # Create a sample JSON payload file
        sample_payload = {
            "data": [
                {
                    "ioc": {
                        "type": "ip",
                        "value": "1.2.3.4"
                    },
                    "detection": {
                        "type": "playbook",
                        "id": "test-id",
                        "name": "Test Detection"
                    }
                }
            ]
        }
        
        json_file = tmpdir / "test.json"
        with open(json_file, "w") as f:
            json.dump(sample_payload, f)
        
        # Create metrics output file
        metrics_file = tmpdir / "metrics.json"
        
        # Mock the async_api_client.send_data method
        with patch("sendDetections.async_api_client.AsyncApiClient.send_data") as mock_send_data:
            # Configure the mock
            mock_response = {
                "summary": {
                    "submitted": 1,
                    "processed": 1,
                    "dropped": 0
                }
            }
            mock_send_data.return_value = mock_response
            
            # Initialize processor with progress bars disabled for testing
            processor = BatchProcessor(
                api_token="test_token",
                show_progress=False
            )
            
            # Process files with metrics export
            result = await processor.process_files(
                [json_file],
                debug=True,
                export_metrics=True,
                metrics_file=metrics_file
            )
            
            # Check results
            assert mock_send_data.called
            assert "summary" in result
            assert result["summary"]["processed"] == 1
            assert "performance" in result
            
            # Check metrics export
            assert metrics_file.exists()
            with open(metrics_file) as f:
                metrics_data = json.load(f)
                assert "api_calls" in metrics_data
                assert "time" in metrics_data
                assert "throughput" in metrics_data


@pytest.mark.asyncio
async def test_process_csv_files_with_metrics():
    """Test processing CSV files with performance metrics."""
    # Create test data
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = Path(tmpdirname)
        
        # Create a sample CSV file
        csv_file = tmpdir / "test.csv"
        csv_content = (
            "Entity,Entity ID,Detectors,Description,Detection Time,Source Type\n"
            "8.8.8.8,ip:8.8.8.8,playbook,Test detection,2023-01-01T10:00:00Z,firewall\n"
        )
        with open(csv_file, "w") as f:
            f.write(csv_content)
        
        # Create metrics output file
        metrics_file = tmpdir / "csv_metrics.json"
        
        # Mock the csv_converter and async_api_client
        with patch("sendDetections.csv_converter.CSVConverter.csv_to_payload") as mock_csv_to_payload:
            with patch("sendDetections.async_api_client.AsyncApiClient.send_data") as mock_send_data:
                # Configure the mocks
                mock_csv_to_payload.return_value = {
                    "data": [
                        {
                            "ioc": {
                                "type": "ip",
                                "value": "8.8.8.8"
                            },
                            "detection": {
                                "type": "playbook",
                                "id": "test-id"
                            }
                        }
                    ]
                }
                
                mock_response = {
                    "summary": {
                        "submitted": 1,
                        "processed": 1,
                        "dropped": 0
                    }
                }
                mock_send_data.return_value = mock_response
                
                # Initialize processor with progress bars disabled for testing
                processor = BatchProcessor(
                    api_token="test_token",
                    show_progress=False
                )
                
                # Process files with metrics export
                result = await processor.process_csv_files(
                    [csv_file],
                    debug=True,
                    export_metrics=True,
                    metrics_file=metrics_file
                )
                
                # Check results
                assert mock_csv_to_payload.called
                assert mock_send_data.called
                assert "summary" in result
                assert result["summary"]["processed"] == 1
                assert "performance" in result
                
                # Check metrics export
                assert metrics_file.exists()
                with open(metrics_file) as f:
                    metrics_data = json.load(f)
                    assert "api_calls" in metrics_data
                    assert "time" in metrics_data
                    assert "throughput" in metrics_data


@pytest.mark.asyncio
async def test_error_handling_in_batch_processing():
    """Test error handling during batch processing."""
    # Create test data
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = Path(tmpdirname)
        
        # Create two sample files - one valid, one that will cause an error
        valid_file = tmpdir / "valid.json"
        error_file = tmpdir / "error.json"
        
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
        
        with open(valid_file, "w") as f:
            json.dump(valid_payload, f)
        
        with open(error_file, "w") as f:
            f.write("{not-valid-json")  # Will cause JSON decode error
        
        # Mock the async_api_client.send_data method
        with patch("sendDetections.async_api_client.AsyncApiClient.send_data") as mock_send_data:
            # Configure the mock
            mock_response = {
                "summary": {
                    "submitted": 1,
                    "processed": 1,
                    "dropped": 0
                }
            }
            mock_send_data.return_value = mock_response
            
            # Initialize processor with progress bars disabled for testing
            processor = BatchProcessor(
                api_token="test_token",
                show_progress=False
            )
            
            # This should fail when trying to read error_file
            with pytest.raises(json.JSONDecodeError):
                await processor.process_files([valid_file, error_file])
            
            # After the error, metrics should still have recorded something
            assert processor.metrics.errors_by_type
            assert "JSONDecodeError" in processor.metrics.errors_by_type


@pytest.mark.asyncio
async def test_process_directory():
    """Test processing all files in a directory."""
    # Create test data
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = Path(tmpdirname)
        
        # Create three files: 2 JSON and 1 TXT
        json_file1 = tmpdir / "test1.json"
        json_file2 = tmpdir / "test2.json"
        txt_file = tmpdir / "test.txt"  # Should be ignored by default pattern
        
        # Create sample JSON payloads
        sample_payload = {
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
        
        with open(json_file1, "w") as f:
            json.dump(sample_payload, f)
            
        with open(json_file2, "w") as f:
            json.dump(sample_payload, f)
            
        with open(txt_file, "w") as f:
            f.write("This is not JSON")
        
        # Mock the batch processor's process_files method
        with patch.object(BatchProcessor, "process_files") as mock_process_files:
            mock_result = {
                "summary": {
                    "submitted": 2,
                    "processed": 2,
                    "dropped": 0
                }
            }
            mock_process_files.return_value = mock_result
            
            # Initialize processor
            processor = BatchProcessor(api_token="test_token", show_progress=False)
            
            # Test with default pattern (*.json)
            result = await processor.process_directory(tmpdir)
            
            # Verify process_files was called with the right files
            mock_process_files.assert_called_once()
            call_args = mock_process_files.call_args[0][0]  # First positional arg is file_paths
            assert len(call_args) == 2
            assert any(f.name == "test1.json" for f in call_args)
            assert any(f.name == "test2.json" for f in call_args)
            assert not any(f.name == "test.txt" for f in call_args)
            
            # Check results were passed through
            assert result == mock_result


@pytest.mark.asyncio
async def test_process_directory_nonexistent():
    """Test processing a nonexistent directory."""
    processor = BatchProcessor(api_token="test_token")
    
    with pytest.raises(FileNotFoundError):
        await processor.process_directory(Path("/nonexistent/directory"))


@pytest.mark.asyncio
async def test_process_directory_empty():
    """Test processing an empty directory."""
    # Create empty directory
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = Path(tmpdirname)
        
        # Initialize processor
        processor = BatchProcessor(api_token="test_token", show_progress=False)
        
        # Process directory
        result = await processor.process_directory(tmpdir)
        
        # Verify result has empty summary
        assert "summary" in result
        assert result["summary"]["submitted"] == 0
        assert result["summary"]["processed"] == 0
        assert result["summary"]["dropped"] == 0


@pytest.mark.asyncio
async def test_process_large_payload():
    """Test processing a large payload by splitting it."""
    # Create a large payload
    large_payload = {
        "data": [
            {
                "ioc": {
                    "type": "ip",
                    "value": f"192.168.0.{i}"
                },
                "detection": {
                    "type": "playbook",
                    "id": f"test-id-{i}"
                }
            }
            for i in range(1, 21)  # 20 items
        ]
    }
    
    # Expected result from split_and_send
    expected_result = {
        "summary": {
            "submitted": 20,
            "processed": 20,
            "dropped": 0
        }
    }
    
    # Mock the client's split_and_send method
    with patch("sendDetections.async_api_client.AsyncApiClient.split_and_send") as mock_split_and_send:
        mock_split_and_send.return_value = expected_result
        
        # Initialize processor with a batch size of 5
        processor = BatchProcessor(
            api_token="test_token",
            batch_size=5,
            show_progress=False
        )
        
        # Process large payload
        result = await processor.process_large_payload(large_payload)
        
        # Verify split_and_send was called with the right arguments
        mock_split_and_send.assert_called_once_with(
            large_payload, 
            batch_size=5,
            debug=False
        )
        
        # Check results
        assert result == expected_result


@pytest.mark.asyncio
async def test_process_large_file():
    """Test processing a large JSON file by splitting its payload."""
    # Create test data
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = Path(tmpdirname)
        
        # Create a JSON file with a large payload
        large_file = tmpdir / "large.json"
        large_payload = {
            "data": [
                {
                    "ioc": {
                        "type": "ip",
                        "value": f"192.168.0.{i}"
                    },
                    "detection": {
                        "type": "playbook",
                        "id": f"test-id-{i}"
                    }
                }
                for i in range(1, 21)  # 20 items
            ]
        }
        
        with open(large_file, "w") as f:
            json.dump(large_payload, f)
        
        # Expected result
        expected_result = {
            "summary": {
                "submitted": 20,
                "processed": 20,
                "dropped": 0
            }
        }
        
        # Mock process_large_payload
        with patch.object(BatchProcessor, "process_large_payload") as mock_process_large_payload:
            mock_process_large_payload.return_value = expected_result
            
            # Initialize processor
            processor = BatchProcessor(api_token="test_token", show_progress=False)
            
            # Process large file
            result = await processor.process_large_file(large_file)
            
            # Verify process_large_payload was called with the right payload
            mock_process_large_payload.assert_called_once()
            assert len(mock_process_large_payload.call_args[0][0]["data"]) == 20
            
            # Check results
            assert result == expected_result


@pytest.mark.asyncio
async def test_process_large_file_not_found():
    """Test handling of nonexistent file in process_large_file."""
    processor = BatchProcessor(api_token="test_token")
    
    with pytest.raises(FileNotFoundError):
        await processor.process_large_file(Path("/nonexistent/file.json"))


@pytest.mark.asyncio
async def test_process_large_file_invalid_json():
    """Test handling of invalid JSON in process_large_file."""
    # Create test data
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = Path(tmpdirname)
        
        # Create a file with invalid JSON
        invalid_file = tmpdir / "invalid.json"
        with open(invalid_file, "w") as f:
            f.write("{not valid json")
        
        # Initialize processor
        processor = BatchProcessor(api_token="test_token", show_progress=False)
        
        # Process file
        with pytest.raises(json.JSONDecodeError):
            await processor.process_large_file(invalid_file)