from collections.abc import Generator
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.db import Base, get_db
from app.models import DocumentDraft, RiskAnalysis, User, UserRole


def test_project_ownership_and_ops_role_boundary() -> None:
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
            first = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "first@example.com",
                    "password": "a-secure-password",
                    "display_name": "第一位用户",
                },
            )
            assert first.status_code == 201
            first_token = first.json()["access_token"]
            project = client.post(
                "/api/v1/app/projects",
                headers={"Authorization": f"Bearer {first_token}"},
                json={"name": "第一项目", "business_description": "测试项目"},
            )
            assert project.status_code == 201
            project_id = project.json()["project_id"]

            second = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "second@example.com",
                    "password": "another-secure-password",
                    "display_name": "第二位用户",
                },
            )
            second_token = second.json()["access_token"]
            forbidden_project = client.get(
                f"/api/v1/app/projects/{project_id}",
                headers={"Authorization": f"Bearer {second_token}"},
            )
            forbidden_ops = client.get(
                "/api/v1/ops/overview", headers={"Authorization": f"Bearer {second_token}"}
            )
            assert forbidden_project.status_code == 403
            assert forbidden_ops.status_code == 403

            with factory() as session:
                second_user = session.query(User).filter_by(email="second@example.com").one()
                session.add(UserRole(user_id=second_user.id, role="operator"))
                session.commit()
            operator_login = client.post(
                "/api/v1/auth/login",
                json={"email": "second@example.com", "password": "another-secure-password"},
            )
            operator_token = operator_login.json()["access_token"]
            allowed_ops = client.get(
                "/api/v1/ops/overview", headers={"Authorization": f"Bearer {operator_token}"}
            )
            assert allowed_ops.status_code == 200
            assert (
                client.get(
                    "/api/v1/admin/users",
                    headers={"Authorization": f"Bearer {operator_token}"},
                ).status_code
                == 403
            )

            with factory() as session:
                second_user = session.query(User).filter_by(email="second@example.com").one()
                session.add(UserRole(user_id=second_user.id, role="admin"))
                session.commit()
            admin_login = client.post(
                "/api/v1/auth/login",
                json={"email": "second@example.com", "password": "another-secure-password"},
            )
            admin_token = admin_login.json()["access_token"]
            created_topic = client.post(
                "/api/v1/ops/learning/topics",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "slug": "product-test",
                    "title": "产品测试主题",
                    "summary": "验证运营内容发布边界。",
                    "body": "这是由受权运营人员创建并发布的测试内容。",
                    "is_published": True,
                },
            )
            assert created_topic.status_code == 201
            public_topics = client.get("/api/v1/app/learn/topics")
            assert any(item["slug"] == "product-test" for item in public_topics.json())

            created_question = client.post(
                "/api/v1/ops/practice/questions",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "title": "运营题目测试",
                    "prompt": "请选择更稳妥的处理方式。",
                    "options": [
                        {"id": "a", "label": "保留检索依据"},
                        {"id": "b", "label": "直接删除依据"},
                    ],
                    "correct_option": "a",
                    "explanation": "初筛结论需要保留可复核的依据。",
                    "difficulty": "basic",
                    "is_published": True,
                },
            )
            assert created_question.status_code == 201
            operator_questions = client.get(
                "/api/v1/ops/practice/questions",
                headers={"Authorization": f"Bearer {operator_token}"},
            )
            assert operator_questions.status_code == 200
            assert operator_questions.json()[0]["correct_option"] == "a"
            assert (
                client.get(
                    "/api/v1/ops/runs", headers={"Authorization": f"Bearer {operator_token}"}
                ).status_code
                == 200
            )

            with factory() as session:
                first_user = session.query(User).filter_by(email="first@example.com").one()
                analysis = RiskAnalysis(
                    owner_id=first_user.id,
                    search_id="search-for-saved-report",
                    analysis_date=date(2026, 7, 21),
                    risk_score=0.4,
                    risk_level="medium",
                    evidence_quality="demo_only",
                    applicable_law_version="demo",
                    methodology={},
                )
                session.add(analysis)
                session.flush()
                draft = DocumentDraft(
                    owner_id=first_user.id,
                    analysis_id=analysis.id,
                    document_type="trademark_registration_risk_report",
                    title="已保存报告",
                    sections=[
                        {"section_id": "summary", "title": "摘要", "content": "可以再次打开。"}
                    ],
                    citations=[],
                    validation_errors=[],
                    warnings=[],
                    facts_snapshot={},
                )
                session.add(draft)
                session.commit()
                analysis_id, document_id = analysis.id, draft.id

            saved = client.get(
                f"/api/v1/app/risk-analyses/{analysis_id}/document",
                headers={"Authorization": f"Bearer {first_token}"},
            )
            assert saved.status_code == 200
            assert saved.json()["document_id"] == document_id
            reused = client.post(
                "/api/v1/app/documents",
                headers={"Authorization": f"Bearer {first_token}"},
                json={
                    "analysis_id": analysis_id,
                    "document_type": "trademark_registration_risk_report",
                },
            )
            assert reused.status_code == 202
            assert reused.json()["resource_id"] == document_id
            exported = client.get(
                f"/api/v1/app/documents/{document_id}/export.pdf",
                headers={"Authorization": f"Bearer {first_token}"},
            )
            assert exported.status_code == 200
            assert exported.content.startswith(b"%PDF")
    finally:
        main_module.app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
