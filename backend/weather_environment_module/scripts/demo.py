"""
Standalone demo script.

Run:
    python scripts/demo.py

Exercises the full pipeline (provider -> processing -> quality -> API
contract) for a handful of North Eastern Region locations, entirely
offline in DEMO_MODE, and prints the resulting risk-feature JSON. This is
what you'd show your SIH teammates / judges to demonstrate the module
without needing the web server running.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DEMO_MODE", "true")

from app.services.environmental_service import EnvironmentalService  # noqa: E402

LOCATIONS = {
    "Gangtok, Sikkim": (27.3389, 88.6065),
    "Shillong, Meghalaya": (25.5788, 91.8933),
    "Aizawl, Mizoram": (23.7271, 92.7176),
    "Itanagar, Arunachal Pradesh": (27.0844, 93.6053),
}


async def main():
    service = EnvironmentalService()
    for name, (lat, lon) in LOCATIONS.items():
        print("=" * 70)
        print(f"{name}  ({lat}, {lon})")
        print("=" * 70)
        response = await service.get_risk_features(lat, lon)
        print(json.dumps(response.model_dump(mode="json"), indent=2))
        print()


if __name__ == "__main__":
    asyncio.run(main())
