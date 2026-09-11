"""
services/feedback_service.py
=============================
Feedback / learning-loop storage.

For this prototype, feedback is stored as a simple JSON list on disk
(backend/data/feedback.json). Each record represents one cycle of:

    Prediction -> Field observation -> Feedback stored -> Calibration dataset updated

We do NOT perform any autonomous model retraining here. The point of this
service is to reliably accumulate ground-truth-labeled examples
(predicted_risk_level vs. landslide_occurred) so that, later, a real
calibration/retraining job can read this same file (or a migrated database)
as its training/validation dataset.

Swapping this for SQLite or a real database later only requires changing
the implementation of `submit_feedback` and `get_all_feedback` — the
function signatures and FeedbackRecord schema can stay the same.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from config import FEEDBACK_FILE
from schemas import FeedbackRecord, FeedbackSubmission


def _ensure_storage_ready(feedback_file: Path) -> None:
    feedback_file.parent.mkdir(parents=True, exist_ok=True)
    if not feedback_file.exists():
        feedback_file.write_text("[]", encoding="utf-8")


def _read_all(feedback_file: Path) -> List[dict]:
    _ensure_storage_ready(feedback_file)
    raw = feedback_file.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    return json.loads(raw)


def _write_all(feedback_file: Path, records: List[dict]) -> None:
    feedback_file.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")


def submit_feedback(
    submission: FeedbackSubmission, feedback_file: Path = FEEDBACK_FILE
) -> FeedbackRecord:
    """Store one feedback submission and return the full stored record."""
    record = FeedbackRecord(
        **submission.model_dump(),
        feedback_id=str(uuid.uuid4()),
        received_at=datetime.now(timezone.utc),
    )

    records = _read_all(feedback_file)
    records.append(json.loads(record.model_dump_json()))
    _write_all(feedback_file, records)

    return record


def get_all_feedback(feedback_file: Path = FEEDBACK_FILE) -> List[FeedbackRecord]:
    """Return every stored feedback record — this is the 'calibration
    dataset' a future retraining job would consume."""
    raw_records = _read_all(feedback_file)
    return [FeedbackRecord(**item) for item in raw_records]
