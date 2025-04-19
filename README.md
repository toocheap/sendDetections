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
  
  # For full installation with all optional dependencies:
  pip install -e ".[full]"
  
  # For YAML configuration support only:
  pip install -e ".[yaml]"
  ```
- Place your sample CSV files in the `sample/` directory
- Set your API token via:
  - `.env` file 
  - `RF_API_TOKEN` environment variable
  - Configuration file (see "Configuration" section)

## Usage

### Example Commands
```sh
# Process files and submit detections
python3 sendDetections.py sample/*.csv --token <YOUR_API_TOKEN>
python3 sendDetections.py sample/*.json --token <YOUR_API_TOKEN>
python3 sendDetections.py sample/*.csv sample/*.json --token <YOUR_API_TOKEN>

# Use with organization ID (must be known in advance)
python3 sendDetections.py sample/*.csv --org-id <YOUR_ORG_ID>

# With advanced options
python3 sendDetections.py sample/*.csv --concurrent 10 --batch-size 200 --export-results
```

### Key Features
- Automatic file type detection (CSV or JSON)
- Multi-organization support for enterprise setups
- Concurrent processing for improved performance
- Comprehensive error analysis and reporting
- Flexible configuration via files, environment variables, or command-line

---

## Running Tests
```sh
pytest tests/
```

---

## Command-Line Options

### Basic Usage
```sh
# Process files and submit detections
python3 sendDetections.py [files...]
```

### Main Parameters
- `[files...]`              Files to process (CSV or JSON files)

### Organization Options
- `--org-id <ID>`           Organization ID to associate with the detections (for multi-org setups)

### API and Authentication Options
- `--token, -t <TOKEN>`     Specify API token (overrides environment/.env/config file)
- `--debug, -d`             Enable debug mode (data not saved to cloud)

### Input Options
- `--input-dir <DIR>`       Directory containing input files (default: sample/)
- `--pattern <PATTERN>`     Filename pattern to match (default: sample_*.csv for CSV files)

### Processing Options
- `--concurrent, -c <N>`    Maximum number of concurrent requests (default: 5)
- `--batch-size, -b <N>`    Maximum number of detections per batch (default: 100)
- `--max-retries, -r <N>`   Maximum number of retry attempts (default: 3)
- `--no-retry`              Disable automatic retries on API errors
- `--no-progress`           Disable progress bars

### Export Options
- `--export-results`        Export processing results to files
- `--export-dir <DIR>`      Directory for exported results (default: current directory)
- `--export-format <FMT>`   Export format: json, csv, html, all (default: all)
- `--export-metrics`        Export performance metrics to a JSON file
- `--metrics-file <FILE>`   Path to save performance metrics (default: auto-generated)
- `--analyze-errors`        Analyze errors and provide suggestions

### Configuration Options
- `--config <PATH>`         Specify a custom configuration file
- `--profile <NAME>`        Use a specific profile from the configuration file (default: "default")

### Logging Options
- `--log-level <LEVEL>`     Set logging level (debug, info, warning, error, critical)
- `--log-file <PATH>`       Write logs to specified file
- `--json-logs`             Output logs in JSON format

## Configuration File Support

sendDetections supports configuration files in both YAML and JSON formats. This allows you to:
- Define different profiles for different environments (dev, staging, prod)
- Store reusable settings to avoid repetitive command-line options
- Configure application behavior globally

### Configuration File Locations

The application looks for configuration files in the following locations (in order):
1. Path specified by `--config` command-line option
2. `senddetections.yml` or `senddetections.yaml` in the project root
3. `senddetections.json` in the project root
4. `~/.config/senddetections.yml`, `~/.config/senddetections.yaml`, or `~/.config/senddetections.json`
5. `~/.senddetections.yml`, `~/.senddetections.yaml`, or `~/.senddetections.json`

### Configuration Format

Example YAML configuration (see `senddetections.yml.example`):
```yaml
# Simple configuration
api_url: https://api.recordedfuture.com/collective-insights/detections
api_options_debug: false
api_options_summary: true
max_concurrent: 5
# For multi-org setups
organization_id: uhash:T2j9L

# Or with profiles:
profiles:
  default:
    api_url: https://api.recordedfuture.com/collective-insights/detections
    api_options_debug: false
  
  dev:
    api_url: https://dev-api.recordedfuture.com/collective-insights/detections
    api_options_debug: true
    max_concurrent: 2
    
  # Profile with organization-specific settings
  org1:
    api_url: https://api.recordedfuture.com/collective-insights/detections
    organization_id: uhash:T2j9L
    max_concurrent: 5
```

Example JSON configuration (see `senddetections.json.example`):
```json
{
  "api_url": "https://api.recordedfuture.com/collective-insights/detections",
  "api_options_debug": false,
  "max_concurrent": 5,
  "organization_id": "uhash:T2j9L",
  
  "profiles": {
    "default": {
      "api_options_debug": false
    },
    "dev": {
      "api_options_debug": true,
      "max_concurrent": 2
    },
    "org1": {
      "organization_id": "uhash:T2j9L",
      "max_concurrent": 5
    }
  }
}
```

### Using Profiles

To use a specific profile from your configuration file:
```sh
python3 sendDetections.py sample/*.json --profile dev
```

### Configuration Priority

Settings are applied in the following order (highest to lowest priority):
1. Command-line arguments
2. Environment variables (prefixed with `RF_`)
3. Configuration file settings
4. Default values

## Data Export

sendDetections can export processing results in various formats:

- JSON: Complete results with detailed information
- CSV: Summary tables for easier analysis
- HTML: Formatted reports with tables and statistics

Use export options to save results for further analysis:

```sh
# Run processing with result export
python3 sendDetections.py sample/*.json --export-results --export-dir ./results

# Analyze errors automatically
python3 sendDetections.py sample/*.csv --analyze-errors
```

## Notes
- The script expects the CSV columns to match the provided sample structure.
- For details on the payload format, see the code or example JSON files.
- YAML configuration requires the PyYAML package (`pip install pyyaml` or `pip install -e ".[yaml]"`)
- Organization IDs must be known in advance; there is no API to list available organizations.

## About the `scripts/` Directory
The `scripts/` directory contains legacy or experimental scripts. These are not required for normal usage, but may be useful for reference or ad-hoc tasks. The main logic for CSV conversion and API submission is in the `sendDetections/` package.