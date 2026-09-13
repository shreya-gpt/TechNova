"""
Cleaning utilities: deduplication, spike detection, and gap-aware
interpolation for hourly environmental series.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

from app.processing.validation import find_duplicate_timestamps


@dataclass
class CleanedSeries:
    timestamps: List[datetime]
    values: List[Optional[float]]
    removed_duplicates: int
    spike_indices: List[int]


def deduplicate_series(timestamps: Sequence[datetime], values: Sequence[Optional[float]]) -> Tuple[List[datetime], List[Optional[float]], int]:
    """Keeps the first occurrence of each timestamp; drops later duplicates."""
    seen = set()
    out_ts: List[datetime] = []
    out_val: List[Optional[float]] = []
    removed = 0
    for t, v in zip(timestamps, values):
        if t in seen:
            removed += 1
            continue
        seen.add(t)
        out_ts.append(t)
        out_val.append(v)
    return out_ts, out_val, removed


def detect_spikes(values: Sequence[Optional[float]], z_threshold: float = 4.0) -> List[int]:
    """
    Flags indices whose value deviates from the series mean by more than
    z_threshold standard deviations. Used as a SUSPICIOUS_SPIKE detector,
    not to silently discard data.
    """
    clean_vals = [v for v in values if v is not None]
    if len(clean_vals) < 4:
        return []
    mean = sum(clean_vals) / len(clean_vals)
    variance = sum((v - mean) ** 2 for v in clean_vals) / len(clean_vals)
    std = variance ** 0.5
    if std == 0:
        return []

    spikes = []
    for i, v in enumerate(values):
        if v is None:
            continue
        z = abs(v - mean) / std
        if z > z_threshold:
            spikes.append(i)
    return spikes


def clean_series(timestamps: Sequence[datetime], values: Sequence[Optional[float]]) -> CleanedSeries:
    dedup_ts, dedup_val, removed = deduplicate_series(timestamps, values)
    spikes = detect_spikes(dedup_val)
    return CleanedSeries(timestamps=dedup_ts, values=dedup_val, removed_duplicates=removed, spike_indices=spikes)
