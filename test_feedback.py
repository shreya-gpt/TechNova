"""
tests/test_feedback.py
========================
Unit tests for backend/services/feedback_service.py and
backend/services/prediction_store.py, exercising the storage layer
directly (independent of the API layer, which is covered in
test_pipeline.py).
"""

import pytest

from backend.mock_data import get_example_ner_request
from backend.pipeline import run_risk_pipeline
from backend.schemas import FeedbackSubmission
from backend.services import prediction_store
from backend.services.feedback_service import (
    PredictionNotFoundError,
    get_all_feedback,
    submit_feedback,
)


def _seed_prediction(predictions_file):
    """Run the real pipeline and persist it, exactly like main.py does,
    so feedback tests reference a genuine prediction_id."""
    result = run_risk_pipeline(get_example_ner_request())
    prediction_store.save_prediction(result, predictions_file=predictions_file)
    return result


def test_submit_feedback_requires_a_known_prediction_id(tmp_path):
    feedback_file = tmp_path / "feedback.json"
    predictions_file = tmp_path / "predictions.json"

    submission = FeedbackSubmission(
        prediction_id="unknown-id",
        observed_condition="No visible change.",
        landslide_occurred=False,
    )

    with pytest.raises(PredictionNotFoundError):
        submit_feedback(submission, feedback_file=feedback_file, predictions_file=predictions_file)


def test_submit_feedback_links_to_existing_prediction(tmp_path):
    feedback_file = tmp_path / "feedback.json"
    predictions_file = tmp_path / "predictions.json"

    prediction = _seed_prediction(predictions_file)

    submission = FeedbackSubmission(
        prediction_id=prediction.prediction_id,
        observed_condition="Saturated soil and minor rockfall observed on the slope.",
        landslide_occurred=True,
        notes="Field team dispatched at 09:00 IST.",
    )

    record = submit_feedback(submission, feedback_file=feedback_file, predictions_file=predictions_file)

    assert record.feedback_id
    assert record.prediction_id == prediction.prediction_id
    assert record.predicted_risk_level == prediction.risk.risk_level
    assert record.location.district == prediction.location.district
    assert record.landslide_occurred is True


def test_feedback_marks_prediction_as_received(tmp_path):
    predictions_file = tmp_path / "predictions.json"
    feedback_file = tmp_path / "feedback.json"

    prediction = _seed_prediction(predictions_file)
    assert prediction_store.get_prediction(prediction.prediction_id, predictions_file)["feedback_status"] == "PENDING"

    submission = FeedbackSubmission(
        prediction_id=prediction.prediction_id,
        observed_condition="No landslide observed after 48h monitoring.",
        landslide_occurred=False,
    )
    submit_feedback(submission, feedback_file=feedback_file, predictions_file=predictions_file)

    updated = prediction_store.get_prediction(prediction.prediction_id, predictions_file)
    assert updated["feedback_status"] == "RECEIVED"


def test_get_all_feedback_returns_all_stored_records(tmp_path):
    feedback_file = tmp_path / "feedback.json"
    predictions_file = tmp_path / "predictions.json"

    prediction_a = _seed_prediction(predictions_file)
    prediction_b = _seed_prediction(predictions_file)

    submit_feedback(
        FeedbackSubmission(
            prediction_id=prediction_a.prediction_id,
            observed_condition="Stable.",
            landslide_occurred=False,
        ),
        feedback_file=feedback_file,
        predictions_file=predictions_file,
    )
    submit_feedback(
        FeedbackSubmission(
            prediction_id=prediction_b.prediction_id,
            observed_condition="Slide occurred overnight.",
            landslide_occurred=True,
        ),
        feedback_file=feedback_file,
        predictions_file=predictions_file,
    )

    records = get_all_feedback(feedback_file=feedback_file)

    assert len(records) == 2
    assert {r.landslide_occurred for r in records} == {True, False}
    assert {r.prediction_id for r in records} == {prediction_a.prediction_id, prediction_b.prediction_id}


def test_feedback_file_is_created_if_missing(tmp_path):
    feedback_file = tmp_path / "nested" / "feedback.json"
    predictions_file = tmp_path / "predictions.json"
    assert not feedback_file.exists()

    prediction = _seed_prediction(predictions_file)
    submit_feedback(
        FeedbackSubmission(
            prediction_id=prediction.prediction_id,
            observed_condition="N/A",
            landslide_occurred=False,
        ),
        feedback_file=feedback_file,
        predictions_file=predictions_file,
    )

    assert feedback_file.exists()
