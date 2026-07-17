from fastapi.testclient import TestClient

import app.main as main_module

client = TestClient(main_module.app)


def test_health_reports_contract_and_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "database_health", lambda: (True, "connected"))
    monkeypatch.setattr(main_module.settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(main_module.settings, "model_runtime_enabled", False)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["contract_version"] == "v0.2"
    assert response.json()["dependencies"]["mysql"]["status"] == "ready"
    assert response.json()["dependencies"]["deepseek"]["status"] == "ready"


def test_invalid_nice_class_uses_shared_error_shape() -> None:
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

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["request_id"].startswith("req_")


def test_arbitrary_source_url_is_not_exposed() -> None:
    paths = {route.path for route in main_module.app.routes}
    assert "/api/v1/sources/{source_key}/sync" in paths
    assert not any("url" in path and "source" in path for path in paths)
