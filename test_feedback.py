"""
tests/test_feedback.py
=======================
Unit tests for services/feedback_service.py, exercising the storage layer
directly (independent of the API layer, which is covered in test_pipeline.py).
"""

from schemas import FeedbackSubmission, Location
from services.feedback_service import get_all_feedback, submit_feedback


def _sample_submission(landslide_occurred: bool = False) -> FeedbackSubmission:
    return FeedbackSubmission(
        prediction_id="pred-001",
        location=Location(latitude=25.28, longitude=91.72, district="East Khasi Hills", state="Meghalaya"),
        predicted_risk_level="HIGH",
        observed_condition="Saturated soil and minor rockfall observed on the slope.",
        landslide_occurred=landslide_occurred,
        notes="Field team dispatched at 09:00 IST.",
    )


def test_submit_feedback_writes_and_returns_record(tmp_path):
    feedback_file = tmp_path / "feedback.json"

    record = submit_feedback(_sample_submission(), feedback_file=feedback_file)

    assert record.feedback_id is not None
    assert record.prediction_id == "pred-001"
    assert record.landslide_occurred is False
    assert feedback_file.exists()


def test_get_all_feedback_returns_all_stored_records(tmp_path):
    feedback_file = tmp_path / "feedback.json"

    submit_feedback(_sample_submission(landslide_occurred=False), feedback_file=feedback_file)
    submit_feedback(_sample_submission(landslide_occurred=True), feedback_file=feedback_file)

    records = get_all_feedback(feedback_file=feedback_file)

    assert len(records) == 2
    assert {r.landslide_occurred for r in records} == {True, False}


def test_feedback_file_is_created_if_missing(tmp_path):
    feedback_file = tmp_path / "nested" / "feedback.json"
    assert not feedback_file.exists()

    submit_feedback(_sample_submission(), feedback_file=feedback_file)

    assert feedback_file.exists()


def test_calibration_dataset_demo_cycle(tmp_path):
    """Demonstrates: Prediction -> Field observation -> Feedback stored ->
    Calibration dataset updated (the dataset is simply the growing list of
    stored FeedbackRecord objects that a future retraining job would read)."""
    feedback_file = tmp_path / "feedback.json"

    assert get_all_feedback(feedback_file=feedback_file) == []

    submit_feedback(_sample_submission(landslide_occurred=True), feedback_file=feedback_file)

    dataset = get_all_feedback(feedback_file=feedback_file)
    assert len(dataset) == 1
    assert dataset[0].landslide_occurred is True
