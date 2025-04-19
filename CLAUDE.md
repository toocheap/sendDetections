# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Process CSV files: `python3 sendDetections.py sample/sample_common.csv`
- Process JSON files: `python3 sendDetections.py detection_input_example.json --token <TOKEN>`
- Process with debug mode: `python3 sendDetections.py sample/*.csv --debug`
- Run tests: `pytest tests/`
- Run single test: `pytest tests/test_sendDetections.py::test_csv_to_payload_conversion`
- Linting: `pylint sendDetections/`
- Type checking: `mypy sendDetections/`

## Code Style Guidelines
- Imports: Group standard library, third-party, and local imports with blank lines between groups
- Types: Use type hints with full annotations from typing module (Dict, List, Optional, etc.)
- Function docstrings: Use triple-quote docstrings with Args/Returns/Raises sections
- Error handling: Use specific exception types with descriptive error messages
- Class structure: Implement business logic in classes with clear methods and responsibilities
- Naming: Use snake_case for variables/functions, PascalCase for classes, UPPER_CASE for constants
- JSON payload: Validate with Pydantic models from validators.py
- API tokens: Use environment variables or .env file via python-dotenv

## CollectiveInsights API detail
Submit indicator detections from security tools to your organisation's Recorded Future enterprise. Collective Insights enriches submissions with Recorded Future intelligence to provide your organisation's enterprise with enhanced and actionable intelligence.

Usage Details
Limit: 15000 submissions per day
Organisations using Collective Insights benefit by having their Recorded Future intelligence enhanced by shared data. In addition, non-attributable data from their submissions can be used to benefit other Recorded Future clients.
Prerequisites
Recorded Future module license
Recorded Future API token for Collective Insights API
Request API Token


Collective Insights API Reference
Collective Insights API - OpenAPI specification


/detections (POST)
Send indicator of compromise detections to Recorded Future Intelligence Cloud. Submissions are associated with the integration user's enterprise and are used to provide enhance intelligence and analytics specific to your enterprise

Parameters

Options (optional)
Configuration parameters

debug (bool)
Whether submissions are saved to Recorded Future Intelligence Cloud

true (default value)
Do not save submissions to Recorded Future Intelligence Cloud (for development and testing)

false
Save submissions to Recorded Future Intelligence Cloud

summary (boolean)
Whether response includes a summary for each submitted indicator
true (default value)
Response includes a summary for each submitted indicator
false
Response will not include a summary for each submitted indicator
organization_ids (array, optional)
Organizations related to submitted indicator detections
data (required)
List or array of indicators of compromise detections
timestamp (str, optional)
Timestamp in ISO 8601 format, for the day and time when the indicator was detected
Default value (If omitted): timestamp of when the API request was sent
ioc (required)
type (str, enum)
Possible values: ip, domain, hash, vulnerability, url
value (str)
Detected indicator of compromise
Example value (for type ip): 8.8.8.8
source_type (optional)
Log source where the detection was made (Known as Event Source in the Recorded Future portal)
field (optional)
Log/event field containing the indicator
 incident (optional)
Link indicator to an incident
id (str)
Example value: "28548e09-63e8-4f8b-abd4-be86207b1583"
name (str)
Example value: "Triggered Detection Rule"
type (str)
Example value: "splunk-detection-rule"
mitre_codes (list, optional)
MITRE codes associated with indicator
malwares (list, optional)
Malware associated with indicator
detection (required)
Indicator detection method
id
Value depends on the type property
If type: correlation
id is the correlation's id (starts with "p_" or "h_")
If type: detection_rule
id is the id of the Recorded Future Analyst note that has the detection rule as an attachment.
Example value: doc:XYZ
If type: playbook
id is the playbook's id
type (str, enum)
How the IOC was detected
Possible values: correlation, playbook, detection_rule, or sandbox
sub_type (required if type: detection_rule)
Possible values: "sigma", "yara", or "snort"
name (optional)
Name of the detection
id (optional)


Example API request
{
   "options": {
      "debug": true,
      "summary": true
   },
   "organization_ids": [
      "uhash:T2j9L"
   ],
   "data": [
      {
         "timestamp": "2023-01-01T10:00:00Z",
         "ioc": {
            "type": "ip",
            "value": "1.2.3.4"
            "source_type": "netscreen:firewall"
         },
         "incident": {
            "id": "28548e09-63e8-4f8b-abd4-be86207b1583",
            "name": "Triggered Detection Rule",
            "type": "splunk-detection-rule"
         },
         "mitre_codes": [
            "T1055"
         ],
         "malwares": [
            "Stuxnet"
         ],
         "detection": {
            "type": "detection_rule",
            "sub_type": "sigma"
            "id" : "doc:r1U_LB"
            "name" : "Priority Malware Detection"
         }
      }
   ]
}

HTTP Response Codes
200
API call was successful
401
Unauthorized (invalid API Token)
403
Forbidden (API Token does not have the required permissions)
500
Internal server error (API service is experiencing issues)

## Collective Insights in a multi-org enterprise


Collective Insights works within a multi-org enterprise; however, setup and configuration must ben tailored to ensure the desired results are achieved.

Some of the specified configuration options must be completed by Recorded Future personnel so please reach out to support@recordedfuture.com if necessary to complete any item.

In a multi-org enterprise, each user will be configured to have access to 1-30 sub-organizations. Each API token is associated with 1 user (known as an integration user) and this integration user will have access to up to 30 organizations. When a detection is submitted from an integration or api, the detection is associated with this integration user and thus with ALL of the organizations this user has access to. That means that the reported detection will be shown on the Secops Dashboard of all other users in that organization.

There are typically 3 configuration options:

1. Multi-org environment for an enterprise where each sub-organization represent a functional group within an enterprise but no privacy is required
In this configuration, detection events will be associated to all sub-organizations and the visibility of collective insights will be dependent upon the user's module configuration

Desired Configuration:

1 integration user (and associated apikey) will be configured and it will have the scope of all sub-organizations in the enterprise
This configuration would typically represent a large enterprise where different organizations were setup for convenience and not for privacy.



2. Multi-org environment for a MSSP where each sub-organization represents a separate customer under management
In this configuration, it is expected that detections are associated with a single sub-organization

Desired Configuration:

Specific integration user (and associated api key) for each sub-org (1 sub-org = 1 key)
This will ensure that detections from customerA are associated with organizationA and only organizationA. The MSSP user may have access to other organizations however only one will be displayed at a time as selected in the portal. A user who only has access to organizationA within Recorded Future will thus only view detections from customerA.

NOTE: This configuration is not restricted to just MSSPs and may be used by multi-org enterprise with such requirements of privacy between sub-organizations



3. Multi-org environment for a MSSP where each sub-organization represents a separate customer under management but alerts are managed centrally by the MSSP

Desired Configuration

1 Integration user with access to all organizations used to pull alerts and NOT used to send detections
1 integration user (and associated api key) for each sub-org (1 sub-org = 1 key) which will be used for sending detections back for that customer
This will allow the MSSP to centrally manage alerts for all clients while still maintaining multi-tenancy across multiple clients for collective insights.

NOTE: Most likely, the 1 integration user for alert will be used on a MSSP owned system for obtaining and triaging the alerts. The 1 integration per customer for collective insights would be installed on/within a customer system for collecting the detection events. In the case of a multi-tenant SIEM (or similar) system, the MSSP will need to ensure the apikey has the right context for sending detections.



4. Multi-org environment for a MSSP where each sub-organization represents a separate customers under management, alerts are managed centrally by the MSSP, and the sub-customers share a common Splunk environment for their detections.

Desired Configuration

1 Integration user with access to all organizations used to pull alerts and used to send detections
Additional configuration on the event source to associate it to each sub-organization as detailed below
By default, all organizations within a multi-org that are accessible from the Recorded Future integration for Splunk will share Collective Insight detection's with each other.

To prevent detection sharing with other organizations, follow the steps below.

Contact Recorded Future support to obtain organization IDs
Open Splunk Enterprise.
Add configuration that adds `rf_multiorg_org=<org-id>` to any event or source where sharing should be limited to a specific organization. This can be done in various ways, ex as a Calculated field (Settings->Fields->Calculated Fields).
Click 'Done'


When using a cloud connector for collective insights rather than an installed integration (i.e. when using the Crowdstrike collective insights connector), when the connector instance is activated an integration is created with access to the selected organization (i.e. the org displayed in the top left corner of the application). This means that the collective insights will be associated to just this organization. If other organizations are added to this integration user (via enterprise settings), then the collective insights will then be associated to all orgs selected. If you want to have the collective insights private to a single org (use-case 2 above), then you should select the relevant organization (top left in the application), configure the collective insights connector instance, and then do not add any other organizations to that integration user in enterprise settings.
