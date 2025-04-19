"""
Data validation for Recorded Future API payloads.
Uses Python 3.10 type annotations and Pydantic v2 for schema validation.
"""

# Use standard library typing (Python 3.10+)
from typing import Any, Optional
# Collections
from collections.abc import Sequence, Mapping

# Pydantic imports
from pydantic import BaseModel, Field, ValidationError, model_validator


class IoC(BaseModel):
    """Indicator of Compromise model."""
    type: str = Field(..., description="Type of IoC (e.g., 'ip', 'domain', 'hash')")
    value: str = Field(..., description="Value of the IoC")
    source_type: Optional[str] = Field(None, description="Log source where the detection was made")
    field: Optional[str] = Field(None, description="Log/event field containing the indicator")
    
    @model_validator(mode='after')
    def validate_ioc_type(self) -> 'IoC':
        """Validate IoC type is one of the allowed values."""
        allowed_types = ["ip", "domain", "hash", "vulnerability", "url"]
        if self.type not in allowed_types:
            raise ValueError(f"IoC type must be one of: {', '.join(allowed_types)}")
        if not self.value:
            raise ValueError("IoC value cannot be empty")
        return self


class Incident(BaseModel):
    """Incident information model."""
    id: Optional[str] = Field(None, description="Incident ID")
    name: Optional[str] = Field(None, description="Incident name")
    type: Optional[str] = Field(None, description="Incident type")


class Detection(BaseModel):
    """Detection method information model."""
    type: str = Field(..., description="How the IoC was detected")
    id: Optional[str] = Field(None, description="ID of the detection")
    name: Optional[str] = Field(None, description="Name of the detection")
    sub_type: Optional[str] = Field(None, description="Subtype of detection (required for detection_rule)")

    @model_validator(mode='after')
    def validate_detection_rule(self) -> 'Detection':
        """Validate that detection_rule type has a sub_type."""
        allowed_types = ["correlation", "playbook", "detection_rule", "sandbox"]
        if self.type not in allowed_types and not self.type.startswith("detector_"):
            raise ValueError(f"Detection type must be one of: {', '.join(allowed_types)} " 
                             f"or start with 'detector_'")
                             
        if self.type == "detection_rule" and not self.sub_type:
            raise ValueError("'sub_type' is required when type is 'detection_rule'")
        return self


class DataEntry(BaseModel):
    """Single detection entry in the payload."""
    ioc: IoC
    detection: Detection
    timestamp: Optional[str] = Field(None, description="Timestamp in ISO 8601 format")
    incident: Optional[Incident] = None
    mitre_codes: Optional[list[str]] = None
    malwares: Optional[list[str]] = None
    
    @model_validator(mode='after')
    def validate_timestamp(self) -> 'DataEntry':
        """Validate timestamp is in ISO 8601 format."""
        if self.timestamp:
            # Very basic ISO8601 validation
            if not (self.timestamp.endswith('Z') and 'T' in self.timestamp and 
                    self.timestamp.replace('T', ':').replace('Z', ':').replace('-', ':').count(':') >= 5):
                raise ValueError("Timestamp must be in ISO 8601 format (YYYY-MM-DDThh:mm:ssZ)")
        return self


class ApiOptions(BaseModel):
    """API options for the request."""
    debug: bool = Field(False, description="Whether submissions are saved to RF Intelligence Cloud")
    summary: bool = Field(True, description="Whether response includes a summary for each indicator")


class ApiPayload(BaseModel):
    """Full API payload model."""
    data: list[DataEntry] = Field(..., min_length=1)
    options: Optional[ApiOptions] = None
    organization_ids: Optional[list[str]] = None


def validate_payload(payload: Mapping[str, Any]) -> Optional[str]:
    """
    Validate a payload dictionary for the Detection API using Pydantic models.
    
    Args:
        payload: The payload dictionary to validate
        
    Returns:
        An error message string if invalid, or None if valid
    """
    try:
        ApiPayload(**payload)
        return None
    except ValidationError as e:
        # Format validation errors nicely
        errors = e.errors()
        if not errors:
            # This case is extremely rare and mainly for defensive programming
            # Occurs if ValidationError is raised but no errors were collected
            return "Unknown validation error"
            
        # Get the first error for simplicity
        error = errors[0]
        location = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        
        return f"Validation error at '{location}': {message}"