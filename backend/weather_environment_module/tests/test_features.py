from datetime import datetime, timedelta, timezone

from app.processing.aggregation import (
    longest_persistent_rain_run,
    rainfall_acceleration,
    rolling_intensity,
    sum_rainfall_last_n_hours,
)
from app.processing.features import (
    antecedent_precipitation_index,
    build_environmental_features,
    build_environmental_indicators,
    rainfall_anomaly_and_percentile,
)


def _hourly_series(hours: int, mm_per_hour: float, now: datetime):
    timestamps = [now - timedelta(hours=h) for h in range(hours, 0, -1)]
    values = [mm_per_hour for _ in timestamps]
    return timestamps, values


def test_sum_rainfall_last_n_hours():
    now = datetime.now(timezone.utc)
    ts, vals = _hourly_series(24, 2.0, now)
    total_24h = sum_rainfall_last_n_hours(ts, vals, now, 24)
    assert total_24h == 48.0

    total_6h = sum_rainfall_last_n_hours(ts, vals, now, 6)
    assert total_6h == 12.0


def test_sum_rainfall_returns_none_when_no_data():
    now = datetime.now(timezone.utc)
    assert sum_rainfall_last_n_hours([], [], now, 24) is None


def test_rolling_intensity():
    now = datetime.now(timezone.utc)
    ts, vals = _hourly_series(6, 3.0, now)
    intensity = rolling_intensity(ts, vals, now, 3)
    assert intensity == 3.0


def test_rainfall_acceleration_intensifying():
    now = datetime.now(timezone.utc)
    # Heavy rain in the last 3h, lighter over the last 12h -> positive acceleration
    ts = [now - timedelta(hours=h) for h in range(12, 0, -1)]
    vals = [1.0] * 9 + [10.0, 10.0, 10.0]
    accel = rainfall_acceleration(ts, vals, now, short_window_hours=3, long_window_hours=12)
    assert accel > 0


def test_antecedent_precipitation_index_decays_older_rain():
    now = datetime.now(timezone.utc)
    # 10mm exactly 1 day ago vs 10mm exactly 10 days ago should contribute
    # more to today's API when it's more recent.
    ts_recent = [now - timedelta(days=1, hours=1)]
    ts_old = [now - timedelta(days=10, hours=1)]

    api_recent = antecedent_precipitation_index(ts_recent, [10.0], now, decay_factor=0.9, lookback_days=15)
    api_old = antecedent_precipitation_index(ts_old, [10.0], now, decay_factor=0.9, lookback_days=15)
    assert api_recent > api_old


def test_antecedent_precipitation_index_none_when_no_data():
    now = datetime.now(timezone.utc)
    assert antecedent_precipitation_index([], [], now) is None


def test_rainfall_anomaly_and_percentile_insufficient_history():
    anomaly, percentile = rainfall_anomaly_and_percentile(50.0, [10.0, 20.0])
    assert anomaly is None and percentile is None


def test_rainfall_anomaly_and_percentile_sufficient_history():
    history = [10.0, 20.0, 30.0, 40.0, 50.0]
    anomaly, percentile = rainfall_anomaly_and_percentile(60.0, history)
    assert anomaly is not None
    assert percentile == 100.0  # exceeds all historical values


def test_longest_persistent_rain_run():
    now = datetime.now(timezone.utc)
    ts = [now - timedelta(hours=h) for h in range(10, 0, -1)]
    vals = [0.0, 0.0, 3.0, 3.0, 3.0, 3.0, 0.0, 5.0, 5.0, 5.0]
    run = longest_persistent_rain_run(ts, vals, min_mm_per_hour=2.0)
    assert run == 4


def test_build_environmental_features_end_to_end():
    now = datetime.now(timezone.utc)
    ts, vals = _hourly_series(72, 5.0, now)
    features = build_environmental_features(
        reference_time=now,
        hist_timestamps=ts,
        hist_rainfall=vals,
        forecast_timestamps=[now + timedelta(hours=h) for h in range(1, 25)],
        forecast_rainfall=[2.0] * 24,
        soil_moisture=0.35,
        temperature_c=24.0,
        relative_humidity_pct=80.0,
    )
    assert features.rainfall_24h_mm == 120.0
    assert features.rainfall_72h_mm == 360.0
    assert features.forecast_rainfall_24h_mm == 48.0
    assert features.soil_moisture_m3m3 == 0.35


def test_build_environmental_indicators_heavy_and_extreme():
    now = datetime.now(timezone.utc)
    ts, vals = _hourly_series(24, 10.0, now)  # 240mm in 24h -> extreme
    features = build_environmental_features(
        reference_time=now,
        hist_timestamps=ts,
        hist_rainfall=vals,
        forecast_timestamps=[],
        forecast_rainfall=[],
        soil_moisture=0.5,
        temperature_c=22.0,
        relative_humidity_pct=90.0,
    )
    indicators = build_environmental_indicators(features, persistent_run_hours=24)
    assert indicators.heavy_rainfall_flag is True
    assert indicators.extreme_accumulation_flag is True
    assert indicators.persistent_rainfall_flag is True
    assert indicators.high_soil_moisture_flag is True
