from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.db import Base, get_db
from app.models import AuditEvent, SourceDefinition, User, UserRole


def test_operator_can_reversibly_exclude_source_from_new_searches() -> None:
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
    try:
        with factory() as session:
            session.add(
                SourceDefinition(
                    source_key="large-official-snapshot",
                    name="国内真实数据集",
                    adapter_type="official_snapshot",
                    license_name="官方开放数据",
                    license_url=None,
                    terms_summary="用于测试可逆检索范围。",
                    allowed_domains=[],
                    enabled=True,
                )
            )
            session.commit()
        with TestClient(main_module.app) as client:
            registered = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "operator-scope@example.com",
                    "password": "a-secure-password",
                    "display_name": "数据运营",
                },
            )
            assert registered.status_code == 201
            with factory() as session:
                user = session.query(User).filter_by(email="operator-scope@example.com").one()
                session.add(UserRole(user_id=user.id, role="operator"))
                session.commit()
            token = client.post(
                "/api/v1/auth/login",
                json={"email": "operator-scope@example.com", "password": "a-secure-password"},
            ).json()["access_token"]
            disabled = client.put(
                "/api/v1/ops/sources/large-official-snapshot/enabled",
                headers={"Authorization": f"Bearer {token}"},
                json={"enabled": False},
            )
            assert disabled.status_code == 200
            assert disabled.json()["enabled"] is False
            restored = client.put(
                "/api/v1/ops/sources/large-official-snapshot/enabled",
                headers={"Authorization": f"Bearer {token}"},
                json={"enabled": True},
            )
            assert restored.status_code == 200
            assert restored.json()["enabled"] is True
        with factory() as session:
            assert session.query(AuditEvent).filter_by(action="source.search_scope.update").count() == 2
    finally:
        main_module.app.dependency_overrides.clear()
