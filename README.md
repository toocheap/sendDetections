# sendDetections

A unified Python tool for converting detection CSV samples into Recorded Future Collective Insights API payload JSON format and submitting them to the API.

## Directory Structure

```
sendDetections/
├── sample/                  # Sample data directory (CSV and converted JSON)
│   ├── sample_common.csv
│   ├── sample_common.json
│   └── ...
├── scripts/                 # Utility/legacy scripts (not required for normal use)
│   └── csv_to_payload_json.py
├── sendDetections/          # Python package (core logic)
│   ├── __init__.py
│   ├── __main__.py
│   ├── api_client.py
│   └── csv_converter.py
├── sendDetections.py        # CLI wrapper script (calls the package)
├── README.md                # This documentation
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Project metadata
└── ...
```

## Prerequisites
- Python 3.10 or later (recommended: use [pyenv](https://github.com/pyenv/pyenv) for version management)
- Use a virtual environment (virtualenv or venv is recommended)
- Install dependencies:
  ```sh
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```
- Place your sample CSV files in the `sample/` directory
- Set your API token via a `.env` file or the `RF_API_TOKEN` environment variable

## Usage

### Example (both are equivalent)
```sh
python3 sendDetections.py convert
python3 -m sendDetections convert
```
- Both commands provide the same CLI functionality.
- The main logic is implemented in the `sendDetections/` package.
- `sendDetections.py` is a CLI wrapper for convenience.

### 1. Convert all CSVs in `sample/` to JSON
```sh
python3 sendDetections.py convert
# or
python3 -m sendDetections convert
```

### 2. Submit a JSON file to the API
```sh
python3 sendDetections.py send sample/sample_common.json --token <YOUR_API_TOKEN>
```
- You can omit `--token` if you set `RF_API_TOKEN` in your environment or `.env` file.
- Add `--debug` to enable debug mode (data will not be submitted to the cloud).

### 3. Convert and submit all in batch
```sh
python3 sendDetections.py convert-send --token <YOUR_API_TOKEN>
```

---

## Running Tests
```sh
pytest tests/
```

---

## Command-Line Options
- `convert [files]`         Convert CSV files to JSON payload format
- `send <files>`            Submit JSON files to the Detection API
- `convert-send [files]`    Convert and send CSV files
- `--token <TOKEN>`         Specify API token (overrides environment/.env)
- `--env-file <PATH>`       Specify custom .env file
- `--debug`                 Enable debug mode (data not saved to cloud)
- `--verbose`               Enable verbose output

## Notes
- The script expects the CSV columns to match the provided sample structure.
- For details on the payload format, see the code or example JSON files.

## About the `scripts/` Directory
The `scripts/` directory contains legacy or experimental scripts. These are not required for normal usage, but may be useful for reference or ad-hoc tasks. The main logic for CSV conversion and API submission is in the `sendDetections/` package.

## Example
```
python3 sendDetections.py convert
python3 sendDetections.py send sample/sample_common.json --token sk-xxx
python3 sendDetections.py convert-send --debug
```
