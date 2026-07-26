from io import BytesIO
from types import SimpleNamespace

import numpy as np
from PIL import Image

from app.config import Settings
from app.retrieval import (
    blob_to_vector,
    course_scenario_visual_score,
    normalize_text,
    normalized_weights,
    is_query_artwork_candidate,
    phash_similarity,
    phonetic_similarity,
    process_image,
    risk_level,
    text_similarity,
    vector_to_blob,
    weighted_score,
)


def test_text_normalization_and_similarity() -> None:
    assert normalize_text(" Ｍａｒｋ-Lens！ ") == "marklens"
    assert text_similarity("马克视界", "马克视界") == 1
    assert phonetic_similarity("知标", "智标") > 0.75


def test_missing_channels_renormalize_weights() -> None:
    scores = {"visual": None, "text": 1.0, "phonetic": 0.8, "semantic": None, "category": 1.0}
    weights = normalized_weights(scores)
    assert round(sum(weights.values()), 5) == 1
    assert "visual" not in weights
    score, applied = weighted_score(scores)
    assert score > 0.8
    assert applied == weights


def test_risk_thresholds_and_insufficient_evidence() -> None:
    assert risk_level(0.75) == "high"
    assert risk_level(0.50) == "medium"
    assert risk_level(0.49) == "low"
    assert risk_level(0.99, has_evidence=False) == "insufficient_evidence"


def test_vector_blob_is_little_endian_float32() -> None:
    vector = np.array([0.25, -1.5, 3.0], dtype=np.float32)
    blob = vector_to_blob(vector)
    restored = blob_to_vector(blob, 3)
    assert restored.dtype == np.dtype("float32")
    np.testing.assert_allclose(restored, vector)


def test_phash_and_image_sanitization(tmp_path) -> None:
    output = BytesIO()
    Image.new("RGB", (80, 60), "white").save(output, "PNG")
    settings = Settings(
        database_url="mysql+pymysql://test:test@localhost/test",
        upload_dir=tmp_path,
        model_runtime_enabled=False,
    )
    processed = process_image(output.getvalue(), "logo.png", settings)
    assert processed.mime_type == "image/png"
    assert processed.width == 80
    assert phash_similarity(processed.phash, processed.phash) == 1


def test_query_artwork_is_not_used_as_its_own_candidate() -> None:
    """A query must never receive a 100% hit from the exact same asset."""
    case = SimpleNamespace(image_asset_id="asset-query")
    candidates = [
        SimpleNamespace(id="self", image_asset_id="asset-query"),
        SimpleNamespace(id="independent", image_asset_id="asset-other"),
        SimpleNamespace(id="text-only", image_asset_id=None),
    ]
    filtered = [item for item in candidates if not is_query_artwork_candidate(case, item)]
    assert [item.id for item in filtered] == ["independent", "text-only"]


def test_course_gradient_scenarios_only_override_the_czech_reference() -> None:
    high_case = SimpleNamespace(facts_snapshot={"showcase_scenario": "cz-gradient-high"})
    low_case = SimpleNamespace(facts_snapshot={"showcase_scenario": "cz-gradient-low"})
    reference = SimpleNamespace(source_record_id="CZ-TM-112187")
    unrelated = SimpleNamespace(source_record_id="CZ-TM-OTHER")

    assert course_scenario_visual_score(high_case, reference) == 0.94
    assert course_scenario_visual_score(low_case, reference) == 0.41
    assert course_scenario_visual_score(high_case, unrelated) is None
