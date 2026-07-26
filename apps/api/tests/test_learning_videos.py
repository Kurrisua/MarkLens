from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.db import Base, get_db
from app.models import LearningTopic, User, UserRole


def test_curated_bilibili_videos_are_public_but_operator_managed() -> None:
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
        with TestClient(main_module.app) as client:
            registration = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "video-operator@example.com",
                    "password": "a-secure-password",
                    "display_name": "视频运营员",
                },
            )
            assert registration.status_code == 201
            with factory() as session:
                user = session.query(User).filter_by(email="video-operator@example.com").one()
                session.add(UserRole(user_id=user.id, role="operator"))
                session.add(
                    LearningTopic(
                        slug="video-topic",
                        title="视频主题",
                        summary="视频测试主题。",
                        is_published=True,
                    )
                )
                session.commit()

            login = client.post(
                "/api/v1/auth/login",
                json={"email": "video-operator@example.com", "password": "a-secure-password"},
            )
            token = login.json()["access_token"]
            invalid = client.post(
                "/api/v1/ops/learning/videos",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "topic_slug": "video-topic",
                    "title": "错误来源",
                    "external_url": "https://example.com/video",
                    "learning_objective": "验证来源限制。",
                    "is_published": True,
                },
            )
            assert invalid.status_code == 422

            created = client.post(
                "/api/v1/ops/learning/videos",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "topic_slug": "video-topic",
                    "title": "商标视频课",
                    "provider": "bilibili",
                    "external_url": "https://www.bilibili.com/video/BV1Hy4y157ra",
                    "duration_label": "外部短课",
                    "learning_objective": "理解初步检索的目的。",
                    "is_published": True,
                },
            )
            assert created.status_code == 201
            assert created.json()["topic_slug"] == "video-topic"

            public = client.get("/api/v1/app/learn/videos")
            assert public.status_code == 200
            assert public.json()[0]["external_url"].startswith("https://www.bilibili.com/")
    finally:
        main_module.app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
