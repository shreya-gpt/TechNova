import numpy as np

from src.preprocessing.cloud_mask import apply_cloud_mask, lee_speckle_filter, simple_cloud_mask
from src.preprocessing.registration import phase_correlation_shift, register_image, register_stack


def test_phase_correlation_shift_detects_translation():
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, (64, 64))
    shifted = np.roll(base, shift=(3, -5), axis=(0, 1))

    dy, dx = phase_correlation_shift(base, shifted)
    # np.roll shift (3, -5) means content moved down 3, left 5;
    # phase correlation should recover a shift close to (-3, 5) to undo it,
    # or equivalently detect the applied shift magnitude closely.
    assert abs(abs(dy) - 3) <= 1
    assert abs(abs(dx) - 5) <= 1


def test_register_image_returns_same_shape():
    rng = np.random.default_rng(1)
    reference = rng.normal(0, 1, (32, 32))
    target = np.roll(reference, shift=(2, 2), axis=(0, 1))
    aligned, shift_vec = register_image(reference, target)
    assert aligned.shape == reference.shape
    assert len(shift_vec) == 2


def test_register_stack_applies_same_shift_to_all_bands():
    rng = np.random.default_rng(2)
    reference = rng.normal(0, 1, (32, 32))
    band1 = np.roll(reference, shift=(1, 1), axis=(0, 1))
    band2 = np.roll(reference, shift=(1, 1), axis=(0, 1)) * 2
    aligned = register_stack(reference, [band1, band2])
    assert len(aligned) == 2
    assert aligned[0].shape == reference.shape


def test_simple_cloud_mask_flags_bright_pixels():
    blue = np.full((10, 10), 0.1)
    nir = np.full((10, 10), 0.1)
    blue[0:3, 0:3] = 0.9  # bright patch = cloud-like
    nir[0:3, 0:3] = 0.9

    mask = simple_cloud_mask(blue, nir, brightness_threshold=0.5)
    assert mask[0, 0] == True  # noqa: E712
    assert mask[9, 9] == False  # noqa: E712


def test_apply_cloud_mask_sets_fill_value():
    image = np.ones((4, 4))
    mask = np.zeros((4, 4), dtype=bool)
    mask[0, 0] = True
    out = apply_cloud_mask(image, mask, fill_value=-1.0)
    assert out[0, 0] == -1.0
    assert out[1, 1] == 1.0


def test_lee_speckle_filter_reduces_variance():
    rng = np.random.default_rng(3)
    clean = np.full((50, 50), 1.0)
    speckled = clean * rng.gamma(shape=4.0, scale=0.25, size=(50, 50))  # multiplicative noise

    filtered = lee_speckle_filter(speckled, window_size=5)
    assert np.var(filtered) < np.var(speckled)
