# services/mcp_server.py
# Placeholder "MCP server" adapter for assignment: exposes tool-like functions.
# In a real MCP server you'd run a separate process; here we simulate calls.
import requests

def get_emergency_numbers(country_code: str = "LK") -> dict:
    # Placeholder: static map for demo; extend with a real API if needed.
    defaults = {"POLICE": "119", "AMBULANCE": "1990", "FIRE": "110"}
    return {"country": country_code, "numbers": defaults}

def get_location_from_maps(query: str) -> dict:
    # Placeholder for a Maps API. Returns a fake, well-formed object.
    return {"query": query, "lat": 6.9271, "lng": 79.8612, "confidence": 0.7}

def call_other_api(name: str, payload: dict) -> dict:
    # Placeholder generic API
    return {"api": name, "ok": True, "echo": payload}
