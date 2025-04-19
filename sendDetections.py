#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unified script for CSV to Payload JSON conversion and Recorded Future Detection API submission.

Usage examples:
  python3 sendDetections.py convert          # Batch convert all sample/*.csv files to .json
  python3 sendDetections.py send sample/sample_common.json --token <TOKEN>
  python3 sendDetections.py convert-send     # Convert and send all CSVs in the sample directory
  
Enhanced features:
  - Structured logging with JSON format option (--json-logs)
  - Detailed error handling with specific error types
  - Automatic retry for transient API errors (--max-retries, --no-retry)
  - Log file support (--log-file)
"""

import sys
from dotenv import load_dotenv

# Import the main function directly from the package
from sendDetections.__main__ import main

# --- For CLI subprocess integration test: requests.post mock ---
if __name__ == "__main__":
    import os
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
                self.headers = {}
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
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Run the main function from the package
    sys.exit(main())


