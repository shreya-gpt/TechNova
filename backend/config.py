"""
config.py
=========
All tunable constants for the PROTOTYPE risk engine live here, in one place,
clearly labeled as placeholders. None of these numbers are scientifically
validated — they exist so the pipeline is fully runnable end-to-end before
a real, calibrated landslide model is integrated.

When the real risk-model teammate's module is ready, `risk_service.py` is
the only file that needs to change (or be replaced entirely) — everything
else in the pipeline just consumes a RiskResult object.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# THIS IS A PROTOTYPE / BASELINE MODEL — NOT A VALIDATED SCIENTIFIC MODEL.
# Weights below are placeholders chosen for demo purposes only.
# ---------------------------------------------------------------------------

# Relative importance of each factor in the weighted risk score.
# These MUST sum to 1.0 — see tests/test_risk_service.py for a check.
RISK_WEIGHTS = {
    "rainfall_24h": 0.18,
    "rainfall_72h": 0.12,
    "forecast_rainfall": 0.10,
    "soil_moisture": 0.15,
    "slope": 0.15,
    "geology": 0.10,
    "historical_landslide_density": 0.10,
    "satellite_surface_change": 0.10,
}

# Human-readable labels used in the explanation text / top_factors list.
FACTOR_LABELS = {
    "rainfall_24h": "elevated 24-hour rainfall",
    "rainfall_72h": "high cumulative 72-hour rainfall",
    "forecast_rainfall": "heavy rainfall forecast ahead",
    "soil_moisture": "high soil moisture/saturation",
    "slope": "steep terrain slope",
    "geology": "weak/unstable geology",
    "historical_landslide_density": "history of past landslide activity",
    "satellite_surface_change": "detected surface change from satellite imagery",
}

# Min/max used to normalize each raw factor onto a 0-1 scale.
# (min, max) — value <= min -> 0.0, value >= max -> 1.0, linear in between.
NORMALIZATION_RANGES = {
    "rainfall_24h": (0.0, 300.0),      # mm
    "rainfall_72h": (0.0, 500.0),      # mm
    "forecast_rainfall": (0.0, 200.0),  # mm
    "soil_moisture": (0.0, 100.0),      # % saturation
    "slope": (0.0, 90.0),               # degrees
    "historical_landslide_density": (0.0, 10.0),  # events per sq km (placeholder scale)
}

# Categorical geology -> normalized instability score (0 = very stable, 1 = very unstable).
GEOLOGY_RISK_MAP = {
    "stable_rock": 0.10,
    "moderately_weathered": 0.40,
    "highly_weathered": 0.70,
    "weak_sedimentary_or_fractured": 0.90,
}
# Used when geology is missing/unrecognized — a neutral mid-point, combined
# with an uncertainty penalty (see risk_service.calculate_uncertainty).
GEOLOGY_DEFAULT_SCORE = 0.5

# risk_score (0-100) thresholds -> RiskLevel
RISK_THRESHOLDS = {
    "LOW": (0, 25),
    "MODERATE": (25, 50),
    "HIGH": (50, 75),
    "CRITICAL": (75, 100.0001),  # upper bound inclusive of 100
}

# ---------------------------------------------------------------------------
# Uncertainty model constants (prototype — see risk_service.calculate_uncertainty)
# ---------------------------------------------------------------------------
BASE_UNCERTAINTY = 0.05
SATELLITE_UNAVAILABLE_PENALTY = 0.15
MISSING_FIELD_PENALTY = 0.05
MAX_UNCERTAINTY = 0.60

# ---------------------------------------------------------------------------
# Impact assessment constants (prototype rule-based exposure fractions)
# ---------------------------------------------------------------------------
IMPACT_EXPOSURE_FRACTION = {
    "LOW": 0.0,
    "MODERATE": 0.15,
    "HIGH": 0.40,
    "CRITICAL": 0.70,
}

# ---------------------------------------------------------------------------
# Feedback storage
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
FEEDBACK_FILE = DATA_DIR / "feedback.json"
