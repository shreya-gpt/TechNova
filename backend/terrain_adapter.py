"""
terrain_adapter.py
===================
BRIDGE between the GIS teammate's DEM code (terrain.py) and the central
risk-engine schema (schemas.py).

Why this file exists:
    terrain.py's get_terrain_data() returns its OWN simple dataclass
    (TerrainData with slope/elevation/geology/historical_landslide_density).
    The risk engine's pipeline expects a schemas.TerrainData (a Pydantic
    model) instead. This file converts one into the other, in ONE place,
    so nobody has to duplicate DEM-reading logic anywhere else.

Usage:
    from terrain_adapter import get_terrain_for_location

    terrain = get_terrain_for_location(
        dem_path="data/terrain/dem.tif",
        latitude=27.30,
        longitude=92.40,
    )
    # terrain is now a schemas.TerrainData, ready to plug into
    # RiskAnalysisRequest(terrain=terrain, ...)
"""

from __future__ import annotations

from typing import Optional

import terrain as dem_terrain          # the GIS teammate's existing module
from schemas import TerrainData        # the risk engine's official schema


def get_terrain_for_location(
    dem_path: str,
    latitude: float,
    longitude: float,
    geology: Optional[str] = None,
    historical_landslide_density: Optional[float] = None,
) -> TerrainData:
    """
    Read slope + elevation for a single point straight out of the DEM file,
    and package it as a schemas.TerrainData that the risk pipeline understands.

    geology / historical_landslide_density are NOT derivable from a DEM
    alone (as terrain.py's own comments say), so they are passed in here
    as optional overrides. Until a real source for them exists, leave them
    as None — the risk engine already knows how to handle that honestly
    (it raises uncertainty instead of guessing).
    """
    raw = dem_terrain.get_terrain_data(dem_path, latitude, longitude)

    return TerrainData(
        slope=raw.slope,
        elevation=raw.elevation,
        geology=geology,
        historical_landslide_density=historical_landslide_density,
    )


if __name__ == "__main__":
    # Quick manual check — matches the same test point used in terrain.py
    result = get_terrain_for_location(
        dem_path="dem.tif",
        latitude=27.30,
        longitude=92.40,
    )
    print("Converted TerrainData ready for the risk engine:")
    print(result.model_dump_json(indent=2))
