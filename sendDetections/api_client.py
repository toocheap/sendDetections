from typing import Optional, TypedDict, Any, Dict, cast
import requests
import sys

API_URL = "https://api.recordedfuture.com/v2/detection/submit"
DEFAULT_HEADERS = {"Content-Type": "application/json"}

Payload = Dict[str, Any]
APIResponse = Dict[str, Any]

class DetectionApiClient:
    @staticmethod
    def validate_payload(payload: Payload) -> Optional[str]:
        if "data" not in payload:
            return "Required field 'data' is missing from the payload."
        if not isinstance(payload["data"], list) or len(payload["data"]) == 0:
            return "'data' field must be a non-empty array."
        for i, entry in enumerate(payload["data"]):
            ioc = entry.get("ioc")
            if not isinstance(ioc, dict):
                return f"Data entry {i+1}: 'ioc' must be a dictionary."
            if not ioc.get("type"):
                return f"Data entry {i+1}: Required field 'type' is missing from 'ioc'."
            if not ioc.get("value"):
                return f"Data entry {i+1}: Required field 'value' is missing from 'ioc'."
            detection = entry.get("detection")
            if not isinstance(detection, dict):
                return f"Data entry {i+1}: 'detection' must be a dictionary."
            if not detection.get("type"):
                return f"Data entry {i+1}: Required field 'type' is missing from 'detection'."
        return None

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
            import traceback
            print(f"Error: An unexpected error occurred while sending data: {str(e)}")
            traceback.print_exc()
            sys.exit(1)
