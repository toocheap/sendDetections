#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified script for CSV to Payload JSON conversion and Recorded Future Detection API submission.

Usage examples:
  python3 sendDetections.py --convert          # Batch convert all sample/*.csv files to .json
  python3 sendDetections.py --send sample/sample_common.json [--token ...]
  python3 sendDetections.py --convert-send     # Convert and send all CSVs in the sample directory
"""

import argparse
import sys
import os
import json as jsonlib
from pathlib import Path
from dotenv import load_dotenv
from sendDetections.csv_converter import CSVConverter
from sendDetections.api_client import DetectionApiClient

# --- For CLI subprocess integration test: requests.post mock ---
if os.environ.get("MOCK_REQUESTS") == "1":
    import requests
    class MockResponse:
        def __init__(self):
            self.status_code = 200
            self._json = {
                "summary": {"submitted": 1, "processed": 1, "dropped": 0, "transient_ids": []},
                "options": {"debug": True}
            }
            self.text = ""
            self.content = b""
        def raise_for_status(self):
            pass
        def json(self):
            return self._json
    def mock_post(url, json, headers, **kwargs):
        # Only assert True if options.debug is specified
        if "options" in json and "debug" in json["options"]:
            assert json["options"]["debug"] is True
        return MockResponse()
    requests.post = mock_post


def parse_arguments():
    parser = argparse.ArgumentParser(description="CSV to Payload JSON conversion and Detection API submission")
    parser.add_argument("--convert", nargs="?", metavar="CSV", help="Convert all CSV files in the sample/ directory to JSON, or a specified CSV file if provided.")
    parser.add_argument("--send", type=str, nargs="*", help="Send specified JSON file(s) to the Detection API")
    parser.add_argument("--convert-send", action="store_true", help="Convert and send all CSV files in the sample/ directory")
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
    if args.convert:
        if isinstance(args.convert, str):
            payload = converter.convert_csv_to_payload_json(Path(args.convert), None, return_payload=True)
            print(jsonlib.dumps(payload, ensure_ascii=False, indent=2))
            return
        else:
            converter.run()
    if args.convert_send:
        converter.run()
    if args.send or args.convert_send:
        if args.send:
            json_files = [Path(f) for f in args.send]
        else:
            json_files = sorted(Path("sample").glob("*.json"))
        if not api_token:
            print("[ERROR] API token is required for sending. Use --token or set RF_API_TOKEN in .env.")
            sys.exit(1)
        for file_path in json_files:
            print(f"[INFO] Sending: {file_path}")
            if args.debug:
                print("Debug mode is enabled")
            with open(file_path, encoding="utf-8") as f:
                payload = jsonlib.load(f)
            err = DetectionApiClient.validate_payload(payload)
            if err:
                print(f"[ERROR] Payload validation failed: {err}")
                continue
            DetectionApiClient.send_data(payload, api_token)

if __name__ == "__main__":
    main()
