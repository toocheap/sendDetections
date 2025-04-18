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
    result = subprocess.run([
        sys.executable, "sendDetections.py", "--convert", str(temp_sample_csv)
    ], capture_output=True, text=True)
    assert result.returncode == 0
    output = result.stdout
    data = json.loads(output)
    assert "data" in data
    assert data["data"][0]["ioc"]["value"] == "2.3.4.5"
    assert data["data"][0]["detection"]["type"] == "detector_b"

def test_cli_send_debug(temp_sample_csv, monkeypatch):
    # Prepare a JSON file using the CLI
    result = subprocess.run([
        sys.executable, "sendDetections.py", "--convert", str(temp_sample_csv)
    ], capture_output=True, text=True, env={**os.environ, 'MOCK_REQUESTS': '1'})
    payload = json.loads(result.stdout)
    json_path = temp_sample_csv.parent / "integration_sample.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    # Set dummy API token
    os.environ["RF_API_TOKEN"] = "dummy-token"
    result = subprocess.run([
        sys.executable, "sendDetections.py", "--send", str(json_path), "--debug"], capture_output=True, text=True, env={**os.environ, 'MOCK_REQUESTS': '1'})
    assert result.returncode == 0
    assert "Debug mode is enabled" in result.stdout
    del os.environ["RF_API_TOKEN"]
