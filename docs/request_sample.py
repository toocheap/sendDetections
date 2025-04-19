import requests

url = "https://api.recordedfuture.com/collective-insights/detections"

payload = {
    "options": { "debug": True },
    "data": [
        {
            "ioc": {
                "value": "10.0.0.1",
                "type": "ip"
            },
            "detection": {
                "name": "ip_correlation_detected",
                "type": "correlation",
                "id": "111222333"
            },
            "mitre_codes": ["T1055"]
        }
    ]
}
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "X-RFToken": "29b5b1d3285946148321e033bde822df"
}

response = requests.post(url, json=payload, headers=headers)

print(response.text)