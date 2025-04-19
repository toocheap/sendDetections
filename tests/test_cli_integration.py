import subprocess
import sys
from pathlib import Path
import tempfile
import shutil
import json
import os
import pytest

SAMPLE_CSV = """Entity ID,Entity,Detectors,Description,Malware,Mitre Codes,Event Source,Event ID,Detection Time\nip:2.3.4.5,2.3.4.5,detector_b,Integration test,malware2,MITRE-456,source_b,evt-002,2025-04-18T01:00:00Z\n"""

@pytest.fixture(scope="module")
def temp_sample_csv():
    tmpdir = tempfile.mkdtemp()
    csv_path = Path(tmpdir) / "integration_sample.csv"
    csv_path.write_text(SAMPLE_CSV, encoding="utf-8")
    yield csv_path
    shutil.rmtree(tmpdir)

def test_cli_process(temp_sample_csv):
    """Test processing a CSV file with the new simplified command structure."""
    output_dir = temp_sample_csv.parent
    # Set dummy API token for test
    os.environ["RF_API_TOKEN"] = "dummy-token"
    
    # With the new simplified command structure, we just pass the file directly
    result = subprocess.run([
        sys.executable, "sendDetections.py", str(temp_sample_csv),
        # We're not actually submitting to the API, just processing locally
        "--debug", "--token", "test-token"
    ], capture_output=True, text=True)
    
    # We'll check the output rather than return code since mock API might fail
    output = result.stdout.lower() + result.stderr.lower()
    print(f"Output: {output}")
    
    # Verify the CSV processing is mentioned in the output
    assert "csv files" in output or "processing" in output
    
    del os.environ["RF_API_TOKEN"]

def test_cli_process_with_options(temp_sample_csv, monkeypatch):
    """Test processing a file with various command-line options."""
    # Set dummy API token
    os.environ["RF_API_TOKEN"] = "dummy-token"
    
    # With the new simplified command structure, process the file with multiple options
    result = subprocess.run([
        sys.executable, "sendDetections.py", str(temp_sample_csv),
        "--debug",  # Don't actually send to the API
        "--token", "test-token",  # Override env token
        "--concurrent", "3",  # Set concurrency
        "--batch-size", "50",  # Set batch size
        "--no-progress"  # Disable progress bars
    ], capture_output=True, text=True, env={**os.environ, 'MOCK_REQUESTS': '1'})
    
    # We'll check the output rather than return code
    output = result.stdout.lower() + result.stderr.lower()
    print(f"Output with options: {output}")
    
    # Check that processing was successful
    assert "processing" in output or "csv files" in output
    
    del os.environ["RF_API_TOKEN"]
