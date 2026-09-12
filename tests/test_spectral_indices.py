import numpy as np

from src.features.spectral_indices import (
    bsi,
    compute_index_delta,
    ndvi,
    ndwi,
    nbr,
    vegetation_loss_fraction,
    water_accumulation_score,
)


def test_ndvi_range():
    nir = np.array([[0.8, 0.2], [0.5, 0.5]])
    red = np.array([[0.2, 0.8], [0.5, 0.5]])
    result = ndvi(nir, red)
    assert result.shape == (2, 2)
    assert np.all(result >= -1.0) and np.all(result <= 1.0)
    # High NIR, low red -> strongly positive NDVI (healthy vegetation)
    assert result[0, 0] > 0.5
    # Low NIR, high red -> strongly negative NDVI
    assert result[0, 1] < -0.5
    # Equal NIR/red -> NDVI ~ 0
    assert abs(result[1, 0]) < 1e-6


def test_ndwi_detects_water():
    green = np.array([[0.6]])
    nir = np.array([[0.1]])
    result = ndwi(green, nir)
    assert result[0, 0] > 0  # green > nir => positive NDWI => likely water


def test_nbr_bare_soil_proxy():
    nir = np.array([[0.2]])
    swir2 = np.array([[0.6]])
    result = nbr(nir, swir2)
    assert result[0, 0] < 0  # low NIR / high SWIR2 => disturbance-like signature


def test_bsi_shape_and_bounds():
    size = (4, 4)
    blue = np.full(size, 0.2)
    red = np.full(size, 0.3)
    nir = np.full(size, 0.5)
    swir1 = np.full(size, 0.3)
    result = bsi(blue, red, nir, swir1)
    assert result.shape == size
    assert np.all(result >= -1.0) and np.all(result <= 1.0)


def test_compute_index_delta():
    pre = np.array([[0.2, 0.5]])
    post = np.array([[0.5, 0.2]])
    delta = compute_index_delta(pre, post)
    np.testing.assert_allclose(delta, [[0.3, -0.3]])


def test_vegetation_loss_fraction_detects_drop():
    ndvi_pre = np.full((10, 10), 0.7)
    ndvi_post = ndvi_pre.copy()
    ndvi_post[:5, :5] = 0.2  # 25 of 100 pixels show a big NDVI drop

    frac = vegetation_loss_fraction(ndvi_pre, ndvi_post, drop_threshold=0.15)
    assert 0.2 <= frac <= 0.3


def test_vegetation_loss_fraction_no_change():
    ndvi_pre = np.full((5, 5), 0.6)
    ndvi_post = ndvi_pre.copy()
    frac = vegetation_loss_fraction(ndvi_pre, ndvi_post)
    assert frac == 0.0


def test_water_accumulation_score_bounds():
    ndwi_pre = np.full((6, 6), -0.2)
    ndwi_post = np.full((6, 6), 0.3)
    score = water_accumulation_score(ndwi_pre, ndwi_post)
    assert 0.0 <= score <= 1.0
    assert score > 0.0
