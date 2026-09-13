from datetime import datetime, timedelta, timezone

from app.processing.validation import (
    data_age_minutes,
    find_duplicate_timestamps,
    find_temporal_gaps,
    is_physically_plausible_rainfall,
    is_plausible_humidity,
    is_plausible_soil_moisture,
    is_plausible_temperature,
    is_stale,
    is_valid_coordinate,
    is_within_ner_bbox,
)


def test_valid_coordinate():
    assert is_valid_coordinate(27.3, 88.6) is True
    assert is_valid_coordinate(91.0, 88.6) is False
    assert is_valid_coordinate(27.3, 200.0) is False
    assert is_valid_coordinate(float("nan"), 88.6) is False


def test_within_ner_bbox_gangtok_sikkim():
    # Gangtok, Sikkim - should be inside the approximate NER bounding box.
    assert is_within_ner_bbox(27.33, 88.61) is True


def test_outside_ner_bbox_mumbai():
    assert is_within_ner_bbox(19.07, 72.87) is False


def test_physically_plausible_rainfall():
    assert is_physically_plausible_rainfall(10.0) is True
    assert is_physically_plausible_rainfall(-5.0) is False
    assert is_physically_plausible_rainfall(500.0, window_hours=1.0) is False
    assert is_physically_plausible_rainfall(None) is True


def test_plausible_temperature_humidity_soil():
    assert is_plausible_temperature(25.0) is True
    assert is_plausible_temperature(100.0) is False
    assert is_plausible_humidity(50.0) is True
    assert is_plausible_humidity(150.0) is False
    assert is_plausible_soil_moisture(0.3) is True
    assert is_plausible_soil_moisture(1.5) is False


def test_duplicate_timestamps():
    now = datetime.now(timezone.utc)
    ts = [now, now, now + timedelta(hours=1)]
    dupes = find_duplicate_timestamps(ts)
    assert dupes == [now]


def test_temporal_gaps():
    now = datetime.now(timezone.utc)
    ts = [now, now + timedelta(hours=1), now + timedelta(hours=5)]
    gaps = find_temporal_gaps(ts, expected_interval_hours=1.0)
    assert len(gaps) == 1


def test_staleness():
    now = datetime.now(timezone.utc)
    fresh = now - timedelta(minutes=10)
    stale = now - timedelta(hours=6)
    assert is_stale(fresh, now=now) is False
    assert is_stale(stale, now=now) is True
    assert data_age_minutes(fresh, now=now) < 15
