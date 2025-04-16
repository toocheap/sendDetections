#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Recorded Future Collective Insights Detection API Submission Script
Usage: python3 sendDetection_script.py detection_input.json
"""

import argparse
import json
import sys
import os
from typing import Dict, Any, Optional, TypedDict, List, Union, cast
import requests
from pathlib import Path
from dotenv import load_dotenv

# Type definitions (Python 3.10+ TypedDict with total=False for optional fields)
class IoC(TypedDict, total=False):
    type: str  # Required
    value: str  # Required
    source_type: str  # Optional
    field: str  # Optional

class Detection(TypedDict, total=False):
    type: str  # Required
    id: str  # Optional
    name: str  # Optional
    sub_type: str  # Optional

class Incident(TypedDict, total=False):
    id: str
    name: str
    type: str

class Options(TypedDict, total=False):
    debug: bool
    summary: bool

class DataEntry(TypedDict, total=False):
    ioc: IoC  # Required
    detection: Detection  # Required
    timestamp: str  # Optional
    mitre_codes: List[str]  # Optional
    malwares: List[str]  # Optional
    incident: Incident  # Optional
    transient_id: str  # Optional

class Payload(TypedDict, total=False):
    data: List[DataEntry]  # Required
    options: Options  # Optional

class APISummary(TypedDict, total=False):
    submitted: int
    processed: int
    dropped: int
    transient_ids: List[str]

class APIResponse(TypedDict, total=False):
    summary: APISummary
    options: Options

# Constants
API_URL = "https://api.recordedfuture.com/collective-insights/detections"
DEFAULT_HEADERS = {
    "accept": "application/json",
    "content-type": "application/json"
}
ENV_TOKEN_KEY = "RF_API_TOKEN"  # Environment variable name

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Send data to Recorded Future Collective Insights Detection API')
    parser.add_argument('input_file', help='JSON file containing data to send')
    parser.add_argument('--token', '-t', help='Recorded Future API token (if not specified, will be obtained from environment variables or user input)')
    parser.add_argument('--env-file', '-e', help='Path to .env file (default is .env in current directory)')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug mode (data will not be saved)')
    return parser.parse_args()

def load_json_file(file_path: str) -> Payload:
    """Load JSON file"""
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

def validate_payload(payload: Payload) -> Optional[str]:
    """Validate payload"""
    # Check required fields
    if "data" not in payload:
        return "Required field 'data' is missing from the payload."
    
    if not isinstance(payload["data"], list) or len(payload["data"]) == 0:
        return "'data' field must be a non-empty array."
    
    # Validate each data entry
    for i, entry in enumerate(payload["data"]):
        # Validate ioc
        if "ioc" not in entry:
            return f"Data entry {i+1}: Required field 'ioc' is missing."
        
        if "type" not in entry["ioc"]:
            return f"Data entry {i+1}: Required field 'type' is missing from 'ioc'."
        
        if "value" not in entry["ioc"]:
            return f"Data entry {i+1}: Required field 'value' is missing from 'ioc'."
        
        # Validate detection
        if "detection" not in entry:
            return f"Data entry {i+1}: Required field 'detection' is missing."
        
        if "type" not in entry["detection"]:
            return f"Data entry {i+1}: Required field 'type' is missing from 'detection'."
        
        # Sub_type is required for detection_rule type
        if entry["detection"]["type"] == "detection_rule" and "sub_type" not in entry["detection"]:
            return f"Data entry {i+1}: 'sub_type' is required for 'detection_rule' type."
    
    return None  # Validation successful

def ensure_debug_mode(payload: Payload, debug_enabled: bool) -> Payload:
    """Ensure debug mode is set properly"""
    # Create options dictionary if it doesn't exist
    if "options" not in payload:
        payload["options"] = {}
    
    # Command line debug flag takes precedence
    if debug_enabled:
        payload["options"]["debug"] = True
    # If debug flag is not specified in payload, default to True (for safety)
    elif "debug" not in payload["options"]:
        payload["options"]["debug"] = True
    
    return payload

def send_data(payload: Payload, api_token: str) -> APIResponse:
    """Send data to API"""
    headers = DEFAULT_HEADERS.copy()
    headers["X-RFToken"] = api_token
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response.raise_for_status()  # Raise exception for 4xx/5xx status codes
        return cast(APIResponse, response.json())
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_msg = ""
        
        try:
            error_data = e.response.json()
            error_msg = error_data.get("message", str(e))
        except:
            error_msg = str(e)
        
        # Using Python 3.10+ match statement
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

def format_response(response: APIResponse) -> None:
    """Format and display API response"""
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
    
    # Display warning if debug mode is enabled
    if response.get("options", {}).get("debug", False):
        print("\nNote: Debug mode is enabled. Data will not be saved to Recorded Future Intelligence Cloud.")
    
    print("\nComplete.")

def get_api_token(args) -> str:
    """
    Get API token
    Priority order:
    1. Command line arguments
    2. Environment variable
    3. .env file
    4. User input
    """
    # 1. From command line args
    if api_token := args.token:
        return api_token
    
    # 2. From environment variable
    if api_token := os.environ.get(ENV_TOKEN_KEY):
        return api_token
    
    # 3. From .env file
    if args.env_file:
        env_path = Path(args.env_file)
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            if api_token := os.environ.get(ENV_TOKEN_KEY):
                return api_token
    else:
        # Default .env file
        default_env = Path('.env')
        if default_env.exists():
            load_dotenv()
            if api_token := os.environ.get(ENV_TOKEN_KEY):
                return api_token
    
    # 4. User input
    return input("Enter Recorded Future API token: ")

def main():
    """Main execution function"""
    args = parse_arguments()
    
    # Load JSON file
    payload = load_json_file(args.input_file)
    
    # Validate payload
    if validation_error := validate_payload(payload):
        print(f"Error: Invalid input data: {validation_error}")
        sys.exit(1)
    
    # Set debug mode
    payload = ensure_debug_mode(payload, args.debug)
    
    # Get API token
    api_token = get_api_token(args)
    
    if not api_token:
        print("Error: No API token provided.")
        sys.exit(1)
    
    # Send data
    print(f"Sending data to Recorded Future Collective Insights API...")
    response = send_data(payload, api_token)
    
    # Display response
    format_response(response)

if __name__ == "__main__":
    main()