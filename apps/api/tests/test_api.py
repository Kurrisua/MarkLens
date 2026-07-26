from fastapi.testclient import TestClient

import app.main as main_module
from app.models import ImageAsset

client = TestClient(main_module.app)


def test_health_reports_contract_and_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "database_health", lambda: (True, "connected"))
    monkeypatch.setattr(main_module.settings, "model_runtime_enabled", False)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["contract_version"] == "v0.2"
    assert response.json()["dependencies"]["mysql"]["status"] == "ready"
    assert response.json()["dependencies"]["user_supplied_ai"]["status"] == "ready"


def test_legacy_unprotected_case_endpoint_is_retired() -> None:
    response = client.post(
        "/api/v1/cases",
        json={
            "trademark_name": "MarkLens",
            "business_description": "演示",
            "nice_classes": [46],
            "image_asset_id": None,
            "confirmed_ocr_text": None,
        },
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "LEGACY_ENDPOINT_RETIRED"
    assert response.json()["error"]["request_id"].startswith("req_")


def test_arbitrary_source_url_is_not_exposed() -> None:
    paths = {route.path for route in main_module.app.routes}
    assert "/api/v1/sources/{source_key}/sync" in paths
    assert not any("url" in path and "source" in path for path in paths)


def test_legacy_image_asset_is_recovered_into_api_storage(tmp_path, monkeypatch) -> None:
    legacy = tmp_path / "data" / "uploads" / "legacy" / "logo.png"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"trusted-image-bytes")
    upload_dir = tmp_path / "apps" / "api" / "data" / "uploads"
    monkeypatch.setattr(main_module, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(main_module.settings, "upload_dir", upload_dir)
    asset = ImageAsset(
        storage_key="legacy/logo.png",
        original_filename="logo.png",
        mime_type="image/png",
        sha256="a" * 64,
        byte_size=19,
        width=1,
        height=1,
    )

    recovered = main_module.resolved_asset_path(asset)

    assert recovered == upload_dir / "legacy" / "logo.png"
    assert recovered.read_bytes() == b"trusted-image-bytes"
