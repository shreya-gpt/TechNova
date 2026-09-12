# Satellite Intelligence & Computer Vision Module
### AI-Based Early Warning and Landslide Risk Monitoring System — North Eastern Region (NER), India
### Smart India Hackathon — Satellite & Computer Vision Sub-System

This repository implements the **Satellite Intelligence and Computer Vision pipeline**
that continuously analyses Sentinel-1 SAR and Sentinel-2 optical imagery to produce
explainable, machine-readable satellite-derived evidence of landslide risk. It is
designed to be one input stream that is fused, by a separate central AI Risk Engine,
with rainfall, soil moisture, slope, geology and historical-landslide data — **this
module never issues a final landslide alert on its own**.

---

## 1. What this module does

```
Satellite Data Acquisition
   → Preprocessing (calibration, terrain correction, cloud masking)
   → Image Registration (co-registration of time-series scenes)
   → Feature Extraction (spectral indices + SAR backscatter/coherence)
   → Change Detection (bi-temporal / Siamese difference model)
   → Landslide Segmentation (U-Net binary mask + confidence)
   → SAR/InSAR Deformation Analysis (phase → displacement proxy)
   → Satellite Risk Indicators (per-AOI engineered feature vector)
   → JSON / GeoJSON output → Central AI Risk Engine + GIS dashboard
```

See `docs/architecture.md` for the full Mermaid architecture diagram and a
stage-by-stage breakdown (input / processing / output / tech / compute cost).

## 2. Repository layout

```
landslide-satellite-cv/
├── config/
│   └── config.yaml              # AOI, thresholds, model paths, API settings
├── src/
│   ├── data_acquisition/        # Sentinel-1 / Sentinel-2 fetch (GEE / SentinelHub)
│   ├── preprocessing/           # registration, cloud/noise masking
│   ├── features/                # NDVI/NDWI/NBR + SAR feature engineering
│   ├── change_detection/        # bi-temporal difference + candidate regions
│   ├── segmentation/            # U-Net landslide segmentation model + training
│   ├── sar_insar/               # simplified InSAR deformation pipeline
│   ├── risk_indicators/         # fuses everything into the output schema
│   ├── api/                     # FastAPI service exposing the module
│   ├── gis/                     # GeoJSON / GeoTIFF / PostGIS export helpers
│   └── utils/                   # geo utilities shared across stages
├── tests/                       # pytest unit tests for every stage
├── scripts/
│   ├── run_pipeline.py          # end-to-end CLI pipeline runner
│   └── demo.py                  # synthetic before/after demo (no internet needed)
├── docs/
│   └── architecture.md          # Mermaid diagram + stage-by-stage design notes
├── requirements.txt
└── README.md
```

## 3. Quick start

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the self-contained demo (generates synthetic before/after tiles,
# runs the full pipeline, prints the output schema, writes a GeoJSON)
python scripts/demo.py

# Run the API
uvicorn src.api.main:app --reload --port 8000
# then POST a scene pair to http://localhost:8000/analyze
```

Run tests:

```bash
pytest -v
```

## 4. Hackathon MVP scope

| Priority | Feature |
|---|---|
| **MUST HAVE** | Sentinel-2 NDVI/NDWI/NBR feature extraction, bi-temporal change detection, U-Net segmentation on a small labeled/synthetic set, JSON output schema, FastAPI `/analyze` endpoint, GeoJSON export |
| **SHOULD HAVE** | Sentinel-1 backscatter change as a cloud-independent fallback, simplified InSAR-style deformation proxy, confidence scoring, PostGIS-ready export |
| **NICE TO HAVE** | True SNAP-based InSAR, embeddings for the risk engine, active-learning loop for scarce labels, road/debris object detector |

## 5. Output schema (module → central AI Risk Engine)

See `src/api/schemas.py` for the authoritative Pydantic model. Summary:

```json
{
  "aoi_id": "NER-MEG-0142",
  "latitude": 25.5788,
  "longitude": 91.8933,
  "observation_date": "2026-09-10",
  "change_score": 0.71,
  "landslide_cv_probability": 0.63,
  "vegetation_loss": 0.24,
  "ndvi_delta": -0.31,
  "ndwi_delta": 0.05,
  "surface_displacement_mm": 18.4,
  "water_accumulation_score": 0.42,
  "road_disruption_score": 0.10,
  "confidence": 0.78,
  "data_sources": ["sentinel-2", "sentinel-1"],
  "explanation": ["18% vegetation loss detected", "..."]
}
```

## 6. Notes on realism for a hackathon build

- Actual Sentinel-1 InSAR normally requires ESA SNAP / GAMMA and multi-pass
  processing that is too heavy for a hackathon timeframe. `src/sar_insar/deformation.py`
  implements a **simplified, clearly-labeled proxy** (coherence-loss + phase-delta
  simulation) that demonstrates the concept and the output contract; swapping in a
  real SNAP-based backend later requires no change to the downstream schema.
- `scripts/demo.py` works fully offline using synthetically generated raster tiles,
  so the whole pipeline can be demoed without live satellite credentials.
- Real acquisition (`src/data_acquisition/sentinel_downloader.py`) is written
  against the Google Earth Engine Python API and Copernicus Open Access Hub as
  the two most hackathon-friendly sources; both require free-tier credentials.
