"""
main.py
=======
FastAPI application entry point.

Run locally (from inside the backend/ folder):

    uvicorn main:app --reload

Endpoints:
    GET  /health          - liveness check
    POST /risk/analyze     - run the full pipeline on a submitted payload
    GET  /risk/example     - run the full pipeline on the built-in NER mock example
    POST /feedback         - submit field-observation feedback
    GET  /feedback         - list all stored feedback records
"""

from __future__ import annotations

from typing import List

from fastapi import FastAPI, HTTPException

from mock_data import get_example_ner_request
from pipeline import run_risk_pipeline
from schemas import (
    FeedbackRecord,
    FeedbackSubmission,
    FinalRiskIntelligence,
    RiskAnalysisRequest,
)
from services.feedback_service import get_all_feedback, submit_feedback

app = FastAPI(
    title="NER Landslide Risk Intelligence & Early Warning Platform — Backend",
    description=(
        "Central integration/backend layer for the SIH 2026 Landslide Risk "
        "Intelligence platform. Combines environmental, terrain, and "
        "satellite inputs into a risk score, uncertainty estimate, "
        "explanation, impact assessment, and recommended actions."
    ),
    version="0.1.0",
)


@app.get("/health", tags=["system"])
def health() -> dict:
    """Simple liveness check."""
    return {"status": "ok"}


@app.post("/risk/analyze", response_model=FinalRiskIntelligence, tags=["risk"])
def analyze_risk(request: RiskAnalysisRequest) -> FinalRiskIntelligence:
    """
    Run the complete pipeline for a single location:
    validation -> data quality -> risk -> uncertainty -> explanation ->
    impact -> recommended action -> FinalRiskIntelligence.

    FastAPI + Pydantic automatically validate the request body against
    RiskAnalysisRequest and return a 422 error for malformed/invalid input
    before this function body ever runs.
    """
    try:
        return run_risk_pipeline(request)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc


@app.get("/risk/example", response_model=FinalRiskIntelligence, tags=["risk"])
def risk_example() -> FinalRiskIntelligence:
    """Run the pipeline against a realistic built-in NER mock example
    (high rainfall, steep slope, weak geology, past landslide history) —
    useful for demos and for teammates who don't have real data wired up yet."""
    example_request = get_example_ner_request()
    return run_risk_pipeline(example_request)


@app.post("/feedback", response_model=FeedbackRecord, tags=["feedback"])
def create_feedback(submission: FeedbackSubmission) -> FeedbackRecord:
    """Submit field-observation feedback for a past prediction. This is the
    'Field observation -> Feedback stored' step of the learning loop."""
    return submit_feedback(submission)


@app.get("/feedback", response_model=List[FeedbackRecord], tags=["feedback"])
def list_feedback() -> List[FeedbackRecord]:
    """Return every stored feedback record (the calibration dataset a future
    retraining job would use)."""
    return get_all_feedback()
