"""
Aggregation utilities for hourly rainfall series: rolling-window sums,
rolling intensity, and simple statistics used by the feature layer.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Sequence, Tuple


def sum_rainfall_last_n_hours(
    timestamps: Sequence[datetime], values: Sequence[Optional[float]], reference_time: datetime, hours: int
) -> Optional[float]:
    """
    Sums rainfall (mm) in the window (reference_time - hours, reference_time].
    Returns None if there is no data at all in the window (vs. 0.0 when the
    window has data but it was all zero rainfall).
    """
    window_start = reference_time - timedelta(hours=hours)
    total = 0.0
    found_any = False
    for t, v in zip(timestamps, values):
        if window_start < t <= reference_time and v is not None:
            total += v
            found_any = True
    return round(total, 2) if found_any else None


def rainfall_intensity(rainfall_mm: Optional[float], hours: float) -> Optional[float]:
    """Average mm/hr over a window."""
    if rainfall_mm is None or hours <= 0:
        return None
    return round(rainfall_mm / hours, 3)


def rolling_intensity(
    timestamps: Sequence[datetime], values: Sequence[Optional[float]], reference_time: datetime, window_hours: int = 3
) -> Optional[float]:
    total = sum_rainfall_last_n_hours(timestamps, values, reference_time, window_hours)
    return rainfall_intensity(total, window_hours)


def rainfall_acceleration(
    timestamps: Sequence[datetime], values: Sequence[Optional[float]], reference_time: datetime,
    short_window_hours: int = 3, long_window_hours: int = 12,
) -> Optional[float]:
    """
    Difference between recent short-window intensity and a longer-window
    baseline intensity (mm/hr^2-ish proxy for "is rainfall speeding up").
    Positive => intensifying; negative => tapering.
    """
    short_intensity = rolling_intensity(timestamps, values, reference_time, short_window_hours)
    long_intensity = rolling_intensity(timestamps, values, reference_time, long_window_hours)
    if short_intensity is None or long_intensity is None:
        return None
    return round(short_intensity - long_intensity, 3)


def longest_persistent_rain_run(
    timestamps: Sequence[datetime], values: Sequence[Optional[float]], min_mm_per_hour: float = 2.0
) -> int:
    """
    Returns the length (in consecutive hourly observations) of the longest
    run where rainfall stayed at or above min_mm_per_hour. Assumes the
    series is roughly hourly and sorted ascending.
    """
    ordered = sorted(zip(timestamps, values), key=lambda p: p[0])
    longest = current = 0
    for _, v in ordered:
        if v is not None and v >= min_mm_per_hour:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest
