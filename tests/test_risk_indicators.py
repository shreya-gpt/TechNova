from datetime import date

from src.risk_indicators.indicator_builder import build_explanation, build_satellite_risk_indicators


def test_build_explanation_includes_relevant_bullets():
    explanation = build_explanation(
        vegetation_loss=0.24,
        surface_displacement_mm=18.4,
        change_score=0.71,
        water_accumulation_score=0.42,
        road_disruption_score=0.10,
    )
    joined = " ".join(explanation)
    assert "24%" in joined
    assert "18.4 mm" in joined
    assert "change score" in joined
    assert "water" in joined.lower()
    # road_disruption_score 0.10 is below the 0.2 reporting threshold
    assert "road" not in joined.lower()


def test_build_explanation_empty_case():
    explanation = build_explanation(
        vegetation_loss=0.0,
        surface_displacement_mm=0.0,
        change_score=0.0,
        water_accumulation_score=0.0,
        road_disruption_score=0.0,
    )
    assert len(explanation) == 1
    assert "No significant" in explanation[0]


def test_build_satellite_risk_indicators_end_to_end():
    result = build_satellite_risk_indicators(
        aoi_id="NER-TEST-001",
        latitude=25.5,
        longitude=91.9,
        observation_date=date(2026, 9, 10),
        change_score=0.71,
        landslide_cv_probability=0.63,
        vegetation_loss=0.24,
        ndvi_delta=-0.31,
        ndwi_delta=0.05,
        surface_displacement_mm=18.4,
        water_accumulation_score=0.42,
        road_disruption_score=0.10,
        cv_confidence=0.8,
        deformation_reliable_fraction=0.9,
        cloud_free_fraction=0.7,
        data_sources=["sentinel-2", "sentinel-1"],
    )
    assert result.aoi_id == "NER-TEST-001"
    assert 0.0 <= result.confidence <= 1.0
    assert "sentinel-1" in result.data_sources
    assert len(result.explanation) >= 1
