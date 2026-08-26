"""Machine-readable metadata for values confirmed in the TD5 dashboard."""

from __future__ import annotations

from typing import Final

# Values not in this catalogue must be shown as unavailable, never invented.
SIGNALS: Final[dict[str, dict[str, str]]] = {
    "rpm": {"label": "Engine speed", "unit": "RPM", "confidence": "verified"},
    "speed_kmh": {"label": "Vehicle speed", "unit": "km/h", "confidence": "verified"},
    "voltage_v": {"label": "Alternator", "unit": "V", "confidence": "verified"},
    "coolant_c": {"label": "Coolant", "unit": "°C", "confidence": "verified"},
    "air_c": {"label": "Inlet air", "unit": "°C", "confidence": "verified"},
    "fuel_c": {"label": "Fuel temp", "unit": "°C", "confidence": "verified"},
    "map_kpa": {"label": "MAP", "unit": "kPa", "confidence": "verified"},
    "aap_kpa": {"label": "Ambient pressure", "unit": "kPa", "confidence": "verified"},
    "maf_kg_h": {"label": "MAF", "unit": "kg/h", "confidence": "verified"},
    "wastegate_percent": {"label": "Wastegate", "unit": "%", "confidence": "verified"},
    "throttle_1": {"label": "Throttle 1", "unit": "V", "confidence": "verified"},
    "injector_balance": {"label": "Injector balance", "unit": "", "confidence": "verified"},
}
