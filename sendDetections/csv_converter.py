#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CSVConverter:
Convert CSV files into JSON payloads for the Detection API.

Uses Python 3.10+ type annotations.
"""

import csv
import json
import logging
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Optional

from sendDetections.config import SAMPLE_DIR, CSV_PATTERN, CSV_ENCODING
from sendDetections.validators import validate_payload

# Configure logger
logger = logging.getLogger(__name__)

class CSVConversionError(Exception):
    """Error occurred during CSV conversion."""
    pass


class CSVConverter:
    """
    Converts CSV rows to API payload entries.
    """
    def __init__(
        self, 
        input_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        csv_pattern: str = CSV_PATTERN,
        encoding: str = CSV_ENCODING
    ):
        """
        Initialize CSV converter with configurable paths.
        
        Args:
            input_dir: Directory containing CSV files (defaults to SAMPLE_DIR)
            output_dir: Directory for output JSON files (defaults to same as input_dir)
            csv_pattern: Glob pattern for matching CSV files
            encoding: File encoding for reading/writing
        """
        self.input_dir = input_dir or SAMPLE_DIR
        self.output_dir = output_dir or self.input_dir
        self.csv_pattern = csv_pattern
        self.encoding = encoding
    
    def find_csv_files(self) -> list[Path]:
        """
        Find CSV files matching the pattern in the input directory.
        
        Returns:
            list of Path objects for matching CSV files
        """
        return sorted(self.input_dir.glob(self.csv_pattern))
    
    def csv_to_payload(self, csv_path: Path) -> dict[str, Any]:
        """
        Read a CSV file and build a payload dict.
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            Dictionary containing the API payload
            
        Raises:
            CSVConversionError: On file access or validation errors
        """
        try:
            with csv_path.open(encoding=self.encoding) as f:
                reader = csv.DictReader(f)
                data = []
                
                for row_num, row in enumerate(reader, start=1):
                    try:
                        entry = self._row_to_entry(row)
                        data.append(entry)
                    except Exception as e:
                        raise CSVConversionError(f"Error in row {row_num}: {str(e)}")
                
            payload = {"data": data}
            
            # Validate the payload
            if (error := validate_payload(payload)):
                raise CSVConversionError(f"Payload validation failed: {error}")
                
            return payload
            
        except (IOError, UnicodeDecodeError) as e:
            raise CSVConversionError(f"Failed to read CSV file: {str(e)}")
            
    def convert_file(self, csv_path: Path, json_path: Optional[Path] = None) -> Path:
        """
        Convert a single CSV file to JSON.
        
        Args:
            csv_path: Path to CSV file
            json_path: Optional output JSON path (defaults to same name with .json extension)
            
        Returns:
            Path to the generated JSON file
            
        Raises:
            CSVConversionError: On conversion errors
        """
        if json_path is None:
            json_path = self.output_dir / csv_path.with_suffix('.json').name
            
        try:
            payload = self.csv_to_payload(csv_path)
            
            # Ensure output directory exists
            json_path.parent.mkdir(parents=True, exist_ok=True)
            
            with json_path.open('w', encoding=self.encoding) as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Converted {csv_path.name} -> {json_path.name}")
            return json_path
            
        except Exception as e:
            raise CSVConversionError(f"Failed to convert {csv_path.name}: {str(e)}")

    def run(self) -> list[Path]:
        """
        Batch-convert all matching CSVs to JSON files.
        
        Returns:
            list of paths to generated JSON files
        """
        csv_files = self.find_csv_files()
        json_files = []
        
        if not csv_files:
            logger.warning(f"No CSV files found matching '{self.csv_pattern}' in {self.input_dir}")
            return []
            
        for csv_file in csv_files:
            try:
                json_path = self.convert_file(csv_file)
                json_files.append(json_path)
            except CSVConversionError as e:
                logger.error(str(e))
                
        return json_files

    def _row_to_entry(self, row: Mapping[str, str]) -> dict[str, Any]:
        """
        Map a CSV row to a payload entry.
        
        Args:
            row: CSV row as dictionary
            
        Returns:
            Entry for the API payload
            
        Raises:
            ValueError: On invalid or missing required data
        """
        # Parse IOC type and value
        entity_id = row.get('Entity ID', '')
        filename = row.get('Source', '')  # Source column might contain type info
        
        # Determine IoC type and value
        if ':' in entity_id:
            # Format: "type:value"
            ioc_type, ioc_value = entity_id.split(':', 1)
        else:
            # Fallback to Entity column or try to infer type from filename
            ioc_value = row.get('Entity', entity_id)
            
            # Try to infer type from filename or Source column
            if "ip" in filename.lower():
                ioc_type = "ip"
            elif "domain" in filename.lower():
                ioc_type = "domain"
            elif "hash" in filename.lower():
                ioc_type = "hash"
            elif "url" in filename.lower():
                ioc_type = "url"
            elif "vuln" in filename.lower():
                ioc_type = "vulnerability"
            else:
                ioc_type = ""  # Empty type will fail validation
        
        # Validate required fields
        if not ioc_type:
            raise ValueError("IoC type is required but could not be determined")
            
        if not ioc_value:
            raise ValueError("IoC value is required but missing")
            
        detector_type = row.get('Detectors', '')
        if not detector_type:
            raise ValueError("Detection type ('Detectors' column) is required but missing")
        
        # Base entry
        entry: dict[str, Any] = {
            'ioc': {
                'type': ioc_type, 
                'value': ioc_value
            },
            'detection': {
                'type': detector_type,
                'name': row.get('Description', ''),
            },
        }
        
        # Add timestamp if present
        if timestamp := row.get('Detection Time', ''):
            entry['timestamp'] = timestamp
            
        # Add source_type to IoC if present
        if source_type := row.get('Source Type', ''):
            entry['ioc']['source_type'] = source_type
            
        # Optional detection sub_type (required for detection_rule)
        if sub_type := row.get('Sub Type', ''):
            entry['detection']['sub_type'] = sub_type
            
        # Optional detection ID
        if detection_id := row.get('Detection ID', ''):
            entry['detection']['id'] = detection_id
        
        # Optional malware list
        malware_str = row.get('Malware') or ''
        malwares = [m.strip() for m in malware_str.split(',') if m.strip()]
        if malwares:
            entry['malwares'] = malwares
            
        # Optional MITRE codes
        mitre_str = row.get('Mitre Codes') or ''
        codes = [c.strip() for c in mitre_str.split(',') if c.strip()]
        if codes:
            entry['mitre_codes'] = codes
            
        # Optional incident
        incident: dict[str, str] = {}
        if event_source := row.get('Event Source', ''):
            incident['type'] = event_source
        if event_id := row.get('Event ID', ''):
            incident['id'] = event_id
        if event_name := row.get('Event Name', ''):
            incident['name'] = event_name
        if incident:
            entry['incident'] = incident
            
        return entry