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

### Example (both are equivalent)
```sh
python3 sendDetections.py submit sample/*.csv
python3 -m sendDetections submit sample/*.csv
```
- Both commands provide the same CLI functionality.
- The main logic is implemented in the `sendDetections/` package.
- `sendDetections.py` is a CLI wrapper for convenience.

### 1. Submit detections from CSV or JSON files
```sh
python3 sendDetections.py submit sample/*.csv --token <YOUR_API_TOKEN>
python3 sendDetections.py submit sample/*.json --token <YOUR_API_TOKEN>
python3 sendDetections.py submit sample/*.csv sample/*.json --token <YOUR_API_TOKEN>
```
- You can omit `--token` if you set `RF_API_TOKEN` in your environment or `.env` file.
- Add `--debug` to enable debug mode (data will not be submitted to the cloud).
- The command automatically detects file types and processes them appropriately.

### 2. Submit with advanced options
```sh
python3 sendDetections.py submit sample/*.csv --concurrent 10 --batch-size 200 --export-results
```
- Process files concurrently with custom parameters
- Export results for analysis

### 3. List available organizations (for multi-org setups)
```sh
python3 sendDetections.py organizations
```
- Lists organizations accessible with your API token
- Useful for multi-organization enterprise setups

---

## Running Tests
```sh
pytest tests/
```

---

## Command-Line Options

### Main Commands
- `submit [files]`          Submit detections (from CSV or JSON files) to RF Intelligence Cloud
- `organizations`           List available organizations (for multi-org setups)

### Common Options
- `--token, -t <TOKEN>`     Specify API token (overrides environment/.env/config file)
- `--debug, -d`             Enable debug mode (data not saved to cloud)
- `--config <PATH>`         Specify a custom configuration file
- `--profile <NAME>`        Use a specific profile from the configuration file (default: "default")

### Logging Options
- `--log-level <LEVEL>`     Set logging level (debug, info, warning, error, critical)
- `--log-file <PATH>`       Write logs to specified file
- `--json-logs`             Output logs in JSON format
- `--no-progress`           Disable progress bars

### Processing Options (for submit command)
- `--concurrent, -c <N>`    Maximum number of concurrent requests (default: 5)
- `--batch-size, -b <N>`    Maximum number of detections per batch (default: 100)
- `--max-retries, -r <N>`   Maximum number of retry attempts (default: 3)
- `--no-retry`              Disable automatic retries on API errors
- `--org-id <ID>`           Organization ID to associate with the detections (for multi-org setups)

### Export Options
- `--export-results`        Export processing results to files
- `--export-dir <DIR>`      Directory for exported results (default: current directory)
- `--export-format <FMT>`   Export format: json, csv, html, all (default: all)
- `--export-metrics`        Export performance metrics to a JSON file
- `--metrics-file <FILE>`   Path to save performance metrics (default: auto-generated)
- `--analyze-errors`        Analyze errors and provide suggestions

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

# Or with profiles:
profiles:
  default:
    api_url: https://api.recordedfuture.com/collective-insights/detections
    api_options_debug: false
  
  dev:
    api_url: https://dev-api.recordedfuture.com/collective-insights/detections
    api_options_debug: true
    max_concurrent: 2
```

Example JSON configuration (see `senddetections.json.example`):
```json
{
  "api_url": "https://api.recordedfuture.com/collective-insights/detections",
  "api_options_debug": false,
  "max_concurrent": 5,
  
  "profiles": {
    "default": {
      "api_options_debug": false
    },
    "dev": {
      "api_options_debug": true,
      "max_concurrent": 2
    }
  }
}
```

### Using Profiles

To use a specific profile from your configuration file:
```sh
python3 sendDetections.py send file.json --profile dev
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
python3 sendDetections.py submit sample/*.json --export-results --export-dir ./results

# Analyze errors automatically
python3 sendDetections.py submit sample/*.csv --analyze-errors
```

## Notes
- The script expects the CSV columns to match the provided sample structure.
- For details on the payload format, see the code or example JSON files.
- YAML configuration requires the PyYAML package (`pip install pyyaml` or `pip install -e ".[yaml]"`)

## About the `scripts/` Directory
The `scripts/` directory contains legacy or experimental scripts. These are not required for normal usage, but may be useful for reference or ad-hoc tasks. The main logic for CSV conversion and API submission is in the `sendDetections/` package.

## Examples
```sh
# New simplified submit command 
python3 sendDetections.py submit sample/*.csv sample/*.json --token sk-xxx
python3 sendDetections.py submit --input-dir data/ --debug

# With organization ID (for multi-org setups)
python3 sendDetections.py submit sample/*.csv --org-id uhash:T2j9L

# With export options
python3 sendDetections.py submit sample/*.json --export-results --analyze-errors

# With custom processing parameters
python3 sendDetections.py submit --concurrent 10 --batch-size 200 --max-retries 5

# With configuration file
python3 sendDetections.py submit sample/*.json --config my-config.yml --profile prod

# Other commands
python3 sendDetections.py organizations  # List available organizations
```