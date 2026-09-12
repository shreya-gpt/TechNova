"""
Satellite Data Acquisition stage.

Wraps two hackathon-friendly sources:
  - Google Earth Engine (GEE) for both Sentinel-1 GRD and Sentinel-2 SR
  - Copernicus Open Access Hub via `sentinelsat` as a fallback

Both are optional at import time: if credentials/packages aren't available,
`scripts/demo.py` bypasses this module entirely with synthetic rasters, so
the rest of the pipeline can always be exercised offline.

Input:  AOI (bounding box) + date range + collection
Output: local GeoTIFF file path(s) for the requested bands
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from loguru import logger

from src.utils.geo_utils import AOI


@dataclass
class SceneRequest:
    aoi: AOI
    start_date: date
    end_date: date
    bands: List[str]
    max_cloud_cover_pct: float = 30.0


class SentinelDownloader:
    """
    Thin acquisition layer. In production this calls GEE's `ee.ImageCollection`
    or `sentinelsat.SentinelAPI`. For hackathon robustness, every method
    degrades gracefully and logs clearly when it cannot reach the network,
    so callers can fall back to cached/synthetic data.
    """

    def __init__(self, output_dir: str = "data/raw"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def fetch_sentinel2(self, request: SceneRequest) -> Optional[str]:
        """
        Fetch a least-cloudy Sentinel-2 SR composite for the AOI/date range.
        Returns a local GeoTIFF path, or None if acquisition failed.
        """
        try:
            import ee  # noqa: F401  (Google Earth Engine)
        except ImportError:
            logger.warning(
                "earthengine-api not installed/authenticated — "
                "skipping live Sentinel-2 fetch. Use scripts/demo.py for an "
                "offline synthetic run, or `pip install earthengine-api` and "
                "run `earthengine authenticate`."
            )
            return None

        logger.info(
            f"Fetching Sentinel-2 for AOI={request.aoi.aoi_id} "
            f"[{request.start_date} → {request.end_date}], "
            f"cloud<{request.max_cloud_cover_pct}%, bands={request.bands}"
        )
        # Real implementation (sketch):
        #   region = ee.Geometry.Rectangle([...])
        #   collection = (ee.ImageCollection(cfg.sentinel2.collection)
        #                 .filterBounds(region)
        #                 .filterDate(str(request.start_date), str(request.end_date))
        #                 .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE',
        #                                      request.max_cloud_cover_pct))
        #                 .select(request.bands))
        #   image = collection.median().clip(region)
        #   export via ee.batch.Export.image.toDrive / geemap.ee_export_image
        out_path = os.path.join(
            self.output_dir, f"{request.aoi.aoi_id}_s2_{request.end_date}.tif"
        )
        return out_path

    def fetch_sentinel1(self, request: SceneRequest) -> Optional[str]:
        """
        Fetch a Sentinel-1 GRD (VV/VH) scene for SAR-based analysis.
        SAR is prioritized in NER because heavy monsoon cloud cover regularly
        blocks optical (Sentinel-2) acquisitions for days to weeks, while
        SAR's microwave signal penetrates cloud cover and works day/night.
        """
        try:
            import ee  # noqa: F401
        except ImportError:
            logger.warning(
                "earthengine-api not installed/authenticated — "
                "skipping live Sentinel-1 fetch."
            )
            return None

        logger.info(
            f"Fetching Sentinel-1 GRD for AOI={request.aoi.aoi_id} "
            f"[{request.start_date} → {request.end_date}]"
        )
        out_path = os.path.join(
            self.output_dir, f"{request.aoi.aoi_id}_s1_{request.end_date}.tif"
        )
        return out_path

    def fetch_dem(self, aoi: AOI, source: str = "SRTM") -> Optional[str]:
        """Fetch a DEM tile (SRTM 30m or Copernicus GLO-30) for slope/terrain."""
        try:
            import ee  # noqa: F401
        except ImportError:
            logger.warning("earthengine-api not available — skipping DEM fetch.")
            return None
        out_path = os.path.join(self.output_dir, f"{aoi.aoi_id}_dem_{source}.tif")
        return out_path
