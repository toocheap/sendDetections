from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import csv
import json

class CSVConverter:
    """
    A class to convert CSV files to Payload JSON format.
    Includes payload validation to ensure compatibility with Detection API requirements.
    """
    # --- Settings ---
    SAMPLE_DIR = Path(__file__).parent.parent / 'sample'
    CSV_PATTERN = 'sample_*.csv'
    CSV_ENCODING = 'utf-8'

    # --- Column name constants ---
    COL_ENTITY_ID = 'Entity ID'
    COL_ENTITY = 'Entity'
    COL_DETECTORS = 'Detectors'
    COL_DESCRIPTION = 'Description'
    COL_MALWARE = 'Malware'
    COL_MITRE_CODES = 'Mitre Codes'
    COL_EVENT_SOURCE = 'Event Source'
    COL_EVENT_ID = 'Event ID'
    COL_DETECTION_TIME = 'Detection Time'

    def __init__(self):
        pass

    @staticmethod
    def validate_payload(payload: Dict[str, Any]) -> Optional[str]:
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

    def parse_ioc_type_and_value(self, entity_id: str, entity: str) -> Tuple[str, str]:
        if ':' in entity_id:
            ioc_type, ioc_value = entity_id.split(':', 1)
            return ioc_type, ioc_value
        return '', entity

    def csv_row_to_dataentry(self, row: Dict[str, str]) -> Dict[str, Any]:
        ioc_type, ioc_value = self.parse_ioc_type_and_value(row.get(self.COL_ENTITY_ID, ''), row.get(self.COL_ENTITY, ''))
        entry = {
            "ioc": {
                "type": ioc_type,
                "value": ioc_value
            },
            "detection": {
                "type": row.get(self.COL_DETECTORS, '') or '',
                "name": row.get(self.COL_DESCRIPTION, '') or ''
            },
            "timestamp": row.get(self.COL_DETECTION_TIME, '') or ''
        }
        malware = [m.strip() for m in row.get(self.COL_MALWARE, '').split(',') if m.strip()]
        if malware:
            entry["malwares"] = malware
        mitre_codes = [m.strip() for m in row.get(self.COL_MITRE_CODES, '').split(',') if m.strip()]
        if mitre_codes:
            entry["mitre_codes"] = mitre_codes
        incident = {}
        if row.get(self.COL_EVENT_SOURCE, ''):
            incident['type'] = row[self.COL_EVENT_SOURCE]
        if row.get(self.COL_EVENT_ID, ''):
            incident['id'] = row[self.COL_EVENT_ID]
        if incident:
            entry['incident'] = incident
        return entry

    def convert_csv_to_payload_json(self, csv_path: Path, json_path: Path) -> None:
        try:
            with csv_path.open(encoding=self.CSV_ENCODING) as f:
                reader = csv.DictReader(f)
                data = [self.csv_row_to_dataentry(row) for row in reader]
            payload = {"data": data}
            err = self.validate_payload(payload)
            if err:
                raise ValueError(f"Payload validation failed: {err}")
            with json_path.open('w', encoding=self.CSV_ENCODING) as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"Converted {csv_path.name} -> {json_path.name}")
        except Exception as e:
            raise Exception(f"[ERROR] {csv_path.name}: {e}")

    def run(self):
        for csv_file in self.SAMPLE_DIR.glob(self.CSV_PATTERN):
            json_file = self.SAMPLE_DIR / (csv_file.stem + '.json')
            self.convert_csv_to_payload_json(csv_file, json_file)
