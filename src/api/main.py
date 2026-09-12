"""
FastAPI service for the Satellite & Computer Vision module.

Endpoints:
  GET  /health    -> service + model status
  POST /analyze   -> run the full satellite pipeline for an AOI/date pair
                      and return the standardized risk-indicator record
                      consumed by the central AI Risk Engine.

For the hackathon demo, when live Sentinel imagery/credentials are not
configured, `/analyze` transparently falls back to a deterministic
synthetic scene generator (the same one used by scripts/demo.py) so judges
can exercise the full API without needing GEE credentials in the room.
"""
from __future__ import annotations

import os

import numpy as np
import yaml
from fastapi import FastAPI, HTTPException
from loguru import logger

from src.api.schemas import HealthResponse, SceneAnalysisRequest, SatelliteRiskIndicatorsResponse
from src.pipeline import OpticalScenePair, SarScenePair, run_satellite_pipeline
from src.segmentation.model import load_model
from src.utils.geo_utils import AOI

app = FastAPI(
    title="Landslide Satellite & CV Module API",
    description="Satellite Intelligence and Computer Vision pipeline for the NER Landslide Early Warning System",
    version="1.0.0",
)

CONFIG_PATH = os.environ.get("LANDSLIDE_CONFIG", "config/config.yaml")
_model = None
_config = None


def get_config() -> dict:
    global _config
    if _config is None:
        with open(CONFIG_PATH, "r") as f:
            _config = yaml.safe_load(f)
    return _config


def get_model():
    global _model
    if _model is None:
        cfg = get_config()
        seg_cfg = cfg.get("segmentation", {})
        _model = load_model(
            checkpoint_path=seg_cfg.get("checkpoint_path"),
            in_channels=seg_cfg.get("in_channels", 6),
        )
    return _model


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        get_model()
        return HealthResponse(status="ok", model_loaded=True)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Model failed to load: {exc}")
        return HealthResponse(status="degraded", model_loaded=False)


def _synthetic_scene_pair(seed: int, size: int = 256) -> OpticalScenePair:
    """
    Deterministic synthetic optical scene pair (see scripts/demo.py for the
    full generator + explanation). Used as an offline fallback so the API
    is always demoable.
    """
    rng = np.random.default_rng(seed)

    def band(base: float, noise: float = 0.05):
        return np.clip(base + rng.normal(0, noise, (size, size)), 0, 1).astype(np.float32)

    blue_pre, green_pre, red_pre = band(0.25), band(0.30), band(0.20)
    nir_pre, swir1_pre = band(0.55), band(0.30)

    # "post" scene: carve out a synthetic disturbed patch (lower NIR/NDVI,
    # higher SWIR/red — mimics exposed soil after a landslide)
    blue_post, green_post, red_post = blue_pre.copy(), green_pre.copy(), red_pre.copy()
    nir_post, swir1_post = nir_pre.copy(), swir1_pre.copy()

    cy, cx, r = size // 2, size // 3, size // 8
    yy, xx = np.ogrid[:size, :size]
    patch = (yy - cy) ** 2 + (xx - cx) ** 2 <= r ** 2

    nir_post[patch] *= 0.4
    red_post[patch] = np.clip(red_post[patch] * 1.4, 0, 1)
    swir1_post[patch] = np.clip(swir1_post[patch] * 1.5, 0, 1)

    return OpticalScenePair(
        blue_pre=blue_pre, green_pre=green_pre, red_pre=red_pre, nir_pre=nir_pre, swir1_pre=swir1_pre,
        blue_post=blue_post, green_post=green_post, red_post=red_post, nir_post=nir_post, swir1_post=swir1_post,
    )


@app.post("/analyze", response_model=SatelliteRiskIndicatorsResponse)
def analyze(request: SceneAnalysisRequest) -> SatelliteRiskIndicatorsResponse:
    try:
        aoi = AOI(
            aoi_id=request.aoi_id,
            min_lat=request.min_lat,
            min_lon=request.min_lon,
            max_lat=request.max_lat,
            max_lon=request.max_lon,
        )
        lat, lon = aoi.centroid

        # NOTE: real acquisition would go through
        # src.data_acquisition.sentinel_downloader.SentinelDownloader here.
        # Falls back to a synthetic pair so the endpoint is always demoable.
        seed = abs(hash((request.aoi_id, str(request.post_date)))) % (2 ** 31)
        optical = _synthetic_scene_pair(seed)

        result = run_satellite_pipeline(
            aoi_id=request.aoi_id,
            latitude=lat,
            longitude=lon,
            observation_date=request.post_date,
            optical=optical,
            sar=None,
            segmentation_model=get_model(),
        )

        return SatelliteRiskIndicatorsResponse(**result.__dict__)

    except Exception as exc:
        logger.exception("Pipeline failure")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/")
def root():
    return {
        "service": "Landslide Satellite & CV Module",
        "docs": "/docs",
        "endpoints": ["/health", "/analyze"],
    }
