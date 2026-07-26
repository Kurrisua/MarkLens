from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.ai_providers import AIConfigurationError, AIRequestConfig
from app.db import Base, get_db


def test_ai_config_requires_https_and_never_exposes_key() -> None:
    with_vision = AIRequestConfig.from_headers(
        {
            "X-Marklens-AI-Provider": "openai_compatible",
            "X-Marklens-AI-Model": "vision-demo",
            "X-Marklens-AI-Key": "private-key-value",
            "X-Marklens-Image-Strategy": "model",
            "X-Marklens-Vision-Enabled": "true",
        }
    )
    assert with_vision.can_review_images is True
    assert "private-key-value" not in repr(with_vision)

    try:
        AIRequestConfig.from_headers(
            {
                "X-Marklens-AI-Provider": "openai_compatible",
                "X-Marklens-AI-Model": "demo",
                "X-Marklens-AI-Key": "private-key-value",
                "X-Marklens-AI-Base-Url": "http://example.test/v1",
            }
        )
    except AIConfigurationError:
        pass
    else:  # pragma: no cover - keeps the assertion message explicit
        raise AssertionError("non-HTTPS custom endpoint must be rejected")


def test_project_advisor_history_is_project_scoped(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def override_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module, "schedule", lambda *_args, **_kwargs: None)
    try:
        with TestClient(main_module.app) as client:
            first = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "advisor-first@example.com",
                    "password": "a-secure-password",
                    "display_name": "项目拥有者",
                },
            )
            first_token = first.json()["access_token"]
            project = client.post(
                "/api/v1/app/projects",
                headers={"Authorization": f"Bearer {first_token}"},
                json={"name": "顾问项目", "business_description": "智能穿戴服务"},
            )
            project_id = project.json()["project_id"]
            created = client.post(
                f"/api/v1/app/projects/{project_id}/advisor/messages",
                headers={"Authorization": f"Bearer {first_token}"},
                json={"question": "这个名称需要先核实哪些注册风险？", "case_id": None},
            )
            assert created.status_code == 202
            assert created.json()["resource_type"] == "consultation"

            own_history = client.get(
                f"/api/v1/app/projects/{project_id}/advisor/messages",
                headers={"Authorization": f"Bearer {first_token}"},
            )
            assert own_history.status_code == 200
            assert own_history.json()[0]["project_id"] == project_id

            second = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "advisor-second@example.com",
                    "password": "another-secure-password",
                    "display_name": "其他用户",
                },
            )
            second_token = second.json()["access_token"]
            forbidden = client.get(
                f"/api/v1/app/projects/{project_id}/advisor/messages",
                headers={"Authorization": f"Bearer {second_token}"},
            )
            assert forbidden.status_code == 403

            invalid_config = client.post(
                f"/api/v1/app/projects/{project_id}/advisor/messages",
                headers={
                    "Authorization": f"Bearer {first_token}",
                    "X-Marklens-AI-Provider": "openai_compatible",
                    "X-Marklens-AI-Model": "demo",
                },
                json={"question": "缺少密钥时必须被拒绝", "case_id": None},
            )
            assert invalid_config.status_code == 422
            assert invalid_config.json()["error"]["code"] == "AI_CONFIGURATION_INVALID"
    finally:
        main_module.app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
