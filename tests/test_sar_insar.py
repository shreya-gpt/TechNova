import numpy as np

from src.sar_insar.deformation import (
    deformation_features,
    phase_to_displacement_mm,
    unwrap_phase_simple,
    wrapped_phase_difference,
)
from src.features.sar_features import backscatter_change, coherence_loss_score, coherence_map


def test_wrapped_phase_difference_range():
    rng = np.random.default_rng(0)
    pre = np.exp(1j * rng.uniform(-np.pi, np.pi, (16, 16)))
    post = np.exp(1j * rng.uniform(-np.pi, np.pi, (16, 16)))
    phase = wrapped_phase_difference(pre, post)
    assert phase.shape == (16, 16)
    assert np.all(phase >= -np.pi - 1e-6) and np.all(phase <= np.pi + 1e-6)


def test_phase_to_displacement_zero_phase_zero_displacement():
    phase = np.zeros((4, 4))
    displacement = phase_to_displacement_mm(phase)
    np.testing.assert_allclose(displacement, 0.0)


def test_unwrap_phase_simple_smooth_ramp():
    ramp = np.tile(np.linspace(-3 * np.pi, 3 * np.pi, 30), (30, 1))
    wrapped = np.angle(np.exp(1j * ramp))
    unwrapped = unwrap_phase_simple(wrapped)
    assert unwrapped.shape == wrapped.shape


def test_deformation_features_reports_reliability_and_limitations():
    rng = np.random.default_rng(1)
    size = 20
    pre = np.exp(1j * rng.uniform(-np.pi, np.pi, (size, size)))
    post = pre.copy()  # perfectly coherent, no real change
    coherence = np.full((size, size), 0.9)

    result = deformation_features(pre, post, coherence, coherence_threshold=0.3)
    assert result.reliable_fraction == 1.0
    assert result.mean_displacement_mm >= 0.0
    assert isinstance(result.limitations, list)
    assert len(result.limitations) >= 1


def test_deformation_features_low_coherence_flags_limitation():
    size = 10
    pre = np.ones((size, size), dtype=complex)
    post = np.ones((size, size), dtype=complex)
    coherence = np.full((size, size), 0.1)  # all below threshold

    result = deformation_features(pre, post, coherence, coherence_threshold=0.3)
    assert result.reliable_fraction == 0.0
    assert any("Low coherence" in msg for msg in result.limitations)


def test_backscatter_change_zero_when_identical():
    vv = np.full((5, 5), 0.5)
    change = backscatter_change(vv, vv)
    np.testing.assert_allclose(change, 0.0, atol=1e-5)


def test_coherence_map_bounds():
    rng = np.random.default_rng(2)
    pre = np.exp(1j * rng.uniform(-np.pi, np.pi, (20, 20)))
    post = np.exp(1j * rng.uniform(-np.pi, np.pi, (20, 20)))
    coherence = coherence_map(pre, post)
    assert coherence.shape == (20, 20)
    assert np.all(coherence >= 0.0) and np.all(coherence <= 1.0)


def test_coherence_loss_score_bounds():
    coherence = np.array([[0.1, 0.9], [0.2, 0.8]])
    score = coherence_loss_score(coherence, threshold=0.3)
    assert 0.0 <= score <= 1.0
    assert score == 0.5  # exactly 2 of 4 pixels below threshold
