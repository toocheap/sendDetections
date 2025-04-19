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

def test_cli_convert(temp_sample_csv):
    output_dir = temp_sample_csv.parent
    result = subprocess.run([
        sys.executable, "sendDetections.py", "convert", str(temp_sample_csv),
        "--output-dir", str(output_dir)
    ], capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {result.stderr}"
    
    # Get the output file path
    output_file = temp_sample_csv.with_suffix('.json')
    assert output_file.exists(), f"Output file {output_file} does not exist"
    
    # Read and verify the JSON content
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    assert "data" in data
    assert data["data"][0]["ioc"]["value"] == "2.3.4.5"
    assert data["data"][0]["detection"]["type"] == "detector_b"

def test_cli_send_debug(temp_sample_csv, monkeypatch):
    output_dir = temp_sample_csv.parent
    # First convert the CSV to JSON
    convert_result = subprocess.run([
        sys.executable, "sendDetections.py", "convert", str(temp_sample_csv),
        "--output-dir", str(output_dir)
    ], capture_output=True, text=True, env={**os.environ, 'MOCK_REQUESTS': '1'})
    assert convert_result.returncode == 0, f"Convert command failed: {convert_result.stderr}"
    
    # Get the output file path
    json_path = temp_sample_csv.with_suffix('.json')
    assert json_path.exists(), f"JSON file {json_path} does not exist"
    
    # Set dummy API token
    os.environ["RF_API_TOKEN"] = "dummy-token"
    
    # Send the JSON file with debug flag
    send_result = subprocess.run([
        sys.executable, "sendDetections.py", "send", str(json_path), "--debug"
    ], capture_output=True, text=True, env={**os.environ, 'MOCK_REQUESTS': '1'})
    
    assert send_result.returncode == 0, f"Send command failed: {send_result.stderr}"
    # Check that the API call was successful - output now goes to stdout
    output = send_result.stdout.lower() + send_result.stderr.lower()
    assert "success" in output or "successfully sent" in output
    
    del os.environ["RF_API_TOKEN"]
