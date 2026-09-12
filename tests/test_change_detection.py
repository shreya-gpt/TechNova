import numpy as np

from src.change_detection.change_detector import (
    candidate_change_mask,
    change_vector_magnitude,
    extract_change_regions,
    overall_change_score,
)


def _synthetic_deltas(size=50):
    """Two delta layers with a clear high-magnitude square region."""
    delta1 = np.random.default_rng(0).normal(0, 0.02, (size, size))
    delta2 = np.random.default_rng(1).normal(0, 0.02, (size, size))
    delta1[10:20, 10:20] = 0.6
    delta2[10:20, 10:20] = 0.5
    return [delta1, delta2]


def test_change_vector_magnitude_shape():
    deltas = _synthetic_deltas()
    magnitude = change_vector_magnitude(deltas)
    assert magnitude.shape == deltas[0].shape
    assert magnitude.min() >= 0


def test_change_vector_magnitude_highlights_region():
    deltas = _synthetic_deltas()
    magnitude = change_vector_magnitude(deltas)
    region_mean = magnitude[10:20, 10:20].mean()
    background_mean = np.delete(magnitude, np.s_[10:20], axis=0).mean()
    assert region_mean > background_mean * 2


def test_candidate_change_mask_adaptive_threshold():
    deltas = _synthetic_deltas()
    magnitude = change_vector_magnitude(deltas)
    mask = candidate_change_mask(magnitude, percentile=90)
    assert mask.dtype == bool
    # The embedded 10x10 region should be captured within the mask
    assert mask[10:20, 10:20].mean() > 0.5


def test_extract_change_regions_filters_small_noise():
    deltas = _synthetic_deltas()
    magnitude = change_vector_magnitude(deltas)
    mask = candidate_change_mask(magnitude, percentile=90)
    regions = extract_change_regions(mask, magnitude, min_area_px=25)
    assert len(regions) >= 1
    largest = regions[0]
    assert largest.pixel_count >= 25
    assert 0.0 <= largest.confidence <= 1.0


def test_extract_change_regions_empty_mask():
    magnitude = np.zeros((20, 20))
    mask = np.zeros((20, 20), dtype=bool)
    regions = extract_change_regions(mask, magnitude)
    assert regions == []


def test_overall_change_score_bounds():
    deltas = _synthetic_deltas()
    magnitude = change_vector_magnitude(deltas)
    mask = candidate_change_mask(magnitude, percentile=90)
    regions = extract_change_regions(mask, magnitude, min_area_px=25)
    score = overall_change_score(regions, image_area_px=magnitude.size)
    assert 0.0 <= score <= 1.0


def test_overall_change_score_zero_when_no_regions():
    score = overall_change_score([], image_area_px=100)
    assert score == 0.0
