#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified script for CSV→Payload JSON conversion and Recorded Future Detection API submission.

Usage examples:
  python3 sendDetections.py --convert          # Batch convert sample/*.csv to .json
  python3 sendDetections.py --send sample/sample_common.json [--token ...]
  python3 sendDetections.py --convert-send     # Convert and send all
"""

import argparse
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from sendDetections.csv_converter import CSVConverter
from sendDetections.api_client import DetectionApiClient


def parse_arguments():
    parser = argparse.ArgumentParser(description="CSV→Payload JSON変換＆Detection API送信")
    parser.add_argument("--convert", action="store_true", help="Convert all CSV files in sample/ to JSON")
    parser.add_argument("--send", type=str, nargs="*", help="Send specified JSON file(s) to Detection API")
    parser.add_argument("--convert-send", action="store_true", help="Convert and send all CSVs in sample/")
    parser.add_argument("--token", type=str, help="Recorded Future API Token (or use .env RF_API_TOKEN)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()


def main():
    args = parse_arguments()
    load_dotenv()
    api_token = args.token or os.getenv("RF_API_TOKEN")
    if not (args.convert or args.send or args.convert_send):
        print("[ERROR] Specify at least one mode: --convert, --send, or --convert-send")
        sys.exit(1)
    converter = CSVConverter()
    if args.convert or args.convert_send:
        converter.run()
    if args.send or args.convert_send:
        # Determine target JSON files
        if args.send:
            json_files = [Path(f) for f in args.send]
        else:
            # All sample/*.json
            json_files = sorted(Path("sample").glob("*.json"))
        if not api_token:
            print("[ERROR] API token is required for sending. Use --token or set RF_API_TOKEN in .env.")
            sys.exit(1)
        for json_path in json_files:
            print(f"[INFO] Sending: {json_path}")
            with open(json_path, encoding="utf-8") as f:
                payload = json.load(f)
            err = DetectionApiClient.validate_payload(payload)
            if err:
                print(f"[ERROR] Payload validation failed: {err}")
                continue
            DetectionApiClient.send_data(payload, api_token)

if __name__ == "__main__":
    main()

class Incident(TypedDict, total=False):
    id: str
    name: str
    type: str

class Options(TypedDict, total=False):
    debug: bool
    summary: bool

class DataEntry(TypedDict, total=False):
    ioc: IoC
    detection: Detection
    timestamp: str
    mitre_codes: List[str]
    malwares: List[str]
    incident: Incident
    transient_id: str

class Payload(TypedDict, total=False):
    data: List[DataEntry]
    options: Options

class APISummary(TypedDict, total=False):
    submitted: int
    processed: int
    dropped: int
    transient_ids: List[str]

class APIResponse(TypedDict, total=False):
    summary: APISummary
    options: Options

# --- Constants ---
API_URL = "https://api.recordedfuture.com/collective-insights/detections"
DEFAULT_HEADERS = {"accept": "application/json", "content-type": "application/json"}
ENV_TOKEN_KEY = "RF_API_TOKEN"
SAMPLE_DIR = Path(__file__).parent / 'sample'
CSV_PATTERN = 'sample_*.csv'
CSV_ENCODING = 'utf-8'

# --- CSV Column Names ---
COL_ENTITY_ID = 'Entity ID'
COL_ENTITY = 'Entity'
COL_DETECTORS = 'Detectors'
COL_DESCRIPTION = 'Description'
COL_MALWARE = 'Malware'
COL_MITRE_CODES = 'Mitre Codes'
COL_EVENT_SOURCE = 'Event Source'
COL_EVENT_ID = 'Event ID'
COL_DETECTION_TIME = 'Detection Time'

class CsvToPayloadConverter:
    @staticmethod
    def parse_ioc_type_and_value(entity_id: str, entity: str) -> tuple[str, str]:
        if ':' in entity_id:
            ioc_type, ioc_value = entity_id.split(':', 1)
            return ioc_type, ioc_value
        return '', entity

    @staticmethod
    def csv_row_to_dataentry(row: Dict[str, str]) -> DataEntry:
        ioc_type, ioc_value = CsvToPayloadConverter.parse_ioc_type_and_value(row.get(COL_ENTITY_ID, ''), row.get(COL_ENTITY, ''))
        entry: DataEntry = {
            "ioc": {"type": ioc_type, "value": ioc_value},
            "detection": {"type": row.get(COL_DETECTORS, '') or '', "name": row.get(COL_DESCRIPTION, '') or ''},
            "timestamp": row.get(COL_DETECTION_TIME, '') or ''
        }
        malware = [m.strip() for m in row.get(COL_MALWARE, '').split(',') if m.strip()]
        if malware:
            entry["malwares"] = malware
        mitre_codes = [m.strip() for m in row.get(COL_MITRE_CODES, '').split(',') if m.strip()]
        if mitre_codes:
            entry["mitre_codes"] = mitre_codes
        incident = {}
        if row.get(COL_EVENT_SOURCE, ''):
            incident['type'] = row[COL_EVENT_SOURCE]
        if row.get(COL_EVENT_ID, ''):
            incident['id'] = row[COL_EVENT_ID]
        if incident:
            entry['incident'] = incident  # type: ignore
        return entry

    @staticmethod
    def csv_to_payload(csv_path: Path) -> Payload:
        """Convert a CSV file to a payload dict (no file output)."""
        with csv_path.open(encoding=CSV_ENCODING) as f:
            reader = csv.DictReader(f)
            data = [CsvToPayloadConverter.csv_row_to_dataentry(row) for row in reader]
        return {"data": data}

    @staticmethod
    def convert_all_csv_in_sample():
        for csv_file in SAMPLE_DIR.glob(CSV_PATTERN):
            json_file = SAMPLE_DIR / (csv_file.stem + '.json')
            # For batch mode, keep legacy file output for compatibility
            payload = CsvToPayloadConverter.csv_to_payload(csv_file)
            with json_file.open('w', encoding=CSV_ENCODING) as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"[OK] Converted {csv_file.name} -> {json_file.name}")

class DetectionApiClient:
    @staticmethod
    def validate_payload(payload: Payload) -> Optional[str]:
        if "data" not in payload:
            return "Required field 'data' is missing from the payload."
        if not isinstance(payload["data"], list) or len(payload["data"]) == 0:
            return "'data' field must be a non-empty array."
        for i, entry in enumerate(payload["data"]):
            # Validate ioc
            ioc = entry.get("ioc")
            if not isinstance(ioc, dict):
                return f"Data entry {i+1}: 'ioc' must be a dictionary."
            if not ioc.get("type"):
                return f"Data entry {i+1}: Required field 'type' is missing from 'ioc'."
            if not ioc.get("value"):
                return f"Data entry {i+1}: Required field 'value' is missing from 'ioc'."
            # Validate detection
            detection = entry.get("detection")
            if not isinstance(detection, dict):
                return f"Data entry {i+1}: 'detection' must be a dictionary."
            if not detection.get("type"):
                return f"Data entry {i+1}: Required field 'type' is missing from 'detection'."
        return None

    @staticmethod
    def ensure_debug_mode(payload: Payload, debug_enabled: bool) -> Payload:
        if debug_enabled:
            options = payload.get("options", {})
            options["debug"] = True
            payload["options"] = options
        return payload

    @staticmethod
    def get_api_token(args) -> str:
        if api_token := getattr(args, 'token', None):
            return api_token
        if api_token := os.environ.get(ENV_TOKEN_KEY):
            return api_token
        if getattr(args, 'env_file', None):
            env_path = Path(args.env_file)
            if env_path.exists():
                load_dotenv(dotenv_path=env_path)
                if api_token := os.environ.get(ENV_TOKEN_KEY):
                    return api_token
        else:
            default_env = Path('.env')
            if default_env.exists():
                load_dotenv()
                if api_token := os.environ.get(ENV_TOKEN_KEY):
                    return api_token
        return input("Enter Recorded Future API token: ")

    @staticmethod
    def send_data(payload: Payload, api_token: str) -> APIResponse:
        try:
            headers = DEFAULT_HEADERS | {"X-RFToken": api_token}
            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return cast(APIResponse, response.json())
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            error_msg = ""
            try:
                error_data = e.response.json()
                error_msg = error_data.get("message", str(e))
            except Exception:
                error_msg = str(e)
            match status_code:
                case 400:
                    print(f"Error (400): Bad Request: {error_msg}")
                case 401:
                    print(f"Error (401): Authentication failed. Check your API token: {error_msg}")
                case 403:
                    print(f"Error (403): Access denied: {error_msg}")
                case 429:
                    print(f"Error (429): Too many requests: {error_msg}")
                case 500:
                    print(f"Error (500): Server internal error: {error_msg}")
                case _:
                    print(f"Error ({status_code}): {error_msg}")
            sys.exit(1)
        except requests.exceptions.ConnectionError:
            print("Error: Cannot connect to API server. Check your internet connection.")
            sys.exit(1)
        except Exception as e:
            print(f"Error: An unexpected error occurred while sending data: {str(e)}")
            sys.exit(1)

    @staticmethod
    def format_response(response: APIResponse) -> None:
        print("\n=== API Response ===")
        print(f"Status: Success")
        if summary := response.get("summary"):
            print("\n=== Submission Summary ===")
            print(f"IoCs submitted: {summary.get('submitted', 0)}")
            print(f"IoCs processed: {summary.get('processed', 0)}")
            if (dropped := summary.get("dropped", 0)) > 0:
                print(f"IoCs dropped: {dropped}")
                if transient_ids := summary.get("transient_ids"):
                    print("\nDropped transaction IDs:")
                    for t_id in transient_ids:
                        print(f"- {t_id}")
        if response.get("options", {}).get("debug", False):
            print("\nNote: Debug mode is enabled. Data will not be saved to Recorded Future Intelligence Cloud.")
        print("\nComplete.")

    @staticmethod
    def load_json_file(file_path: str) -> Payload:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return cast(Payload, json.load(f))
        except json.JSONDecodeError:
            print(f"Error: File '{file_path}' is not a valid JSON format.")
            sys.exit(1)
        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found.")
            sys.exit(1)
        except Exception as e:
            print(f"Error: An error occurred while reading file '{file_path}': {str(e)}")
            sys.exit(1)

# --- Command-line Arguments ---
def parse_arguments():
    parser = argparse.ArgumentParser(description='Convert detection CSV to JSON payload and/or submit to Recorded Future API.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--convert', metavar='CSV', nargs=1, help='Convert specified CSV file to JSON payload and print to stdout')
    group.add_argument('--send', metavar='FILE', help='Send specified JSON or CSV file to API (CSV is converted internally)')
    group.add_argument('--convert-send', action='store_true', help='Batch convert all sample/*.csv and send all')
    parser.add_argument('--token', '-t', help='API token')
    parser.add_argument('--env-file', '-e', help='Path to .env file')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug mode (data not saved to cloud)')
    return parser.parse_args()

# --- Main Entry Point ---
def main():
    args = parse_arguments()
    if args.convert:
        # Convert specified CSV to JSON payload and print to stdout
        csv_path = Path(args.convert[0])
        payload = CsvToPayloadConverter.csv_to_payload(csv_path)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if args.send:
        file_path = Path(args.send)
        if file_path.suffix.lower() == '.csv':
            payload = CsvToPayloadConverter.csv_to_payload(file_path)
        else:
            payload = DetectionApiClient.load_json_file(str(file_path))
        if err := DetectionApiClient.validate_payload(payload):
            print(f"[ERROR] Invalid input data: {err}")
            sys.exit(1)
        payload = DetectionApiClient.ensure_debug_mode(payload, args.debug)
        api_token = DetectionApiClient.get_api_token(args)
        print(f"Sending data to Recorded Future Collective Insights API...")
        response = DetectionApiClient.send_data(payload, api_token)
        DetectionApiClient.format_response(response)
        return
    if args.convert_send:
        CsvToPayloadConverter.convert_all_csv_in_sample()
        for json_file in SAMPLE_DIR.glob('sample_*.json'):
            payload = DetectionApiClient.load_json_file(str(json_file))
            if err := DetectionApiClient.validate_payload(payload):
                print(f"[ERROR] {json_file.name} Invalid input data: {err}")
                continue
            payload = DetectionApiClient.ensure_debug_mode(payload, args.debug)
            api_token = DetectionApiClient.get_api_token(args)
            print(f"Sending {json_file.name} ...")
            response = DetectionApiClient.send_data(payload, api_token)
            DetectionApiClient.format_response(response)
        return

if __name__ == '__main__':
    main()


