import os

import pytest
from sqlalchemy import func, select

from app.db import database_health, get_session_factory
from app.models import AgentRun, CaseRecord, SearchHit, SearchRecord, Trademark
from app.seed import seed_all
from app.services import build_search_operation, create_agent_run, execute_agent

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MYSQL_TESTS") != "true",
    reason="RUN_MYSQL_TESTS=true is required for MySQL integration tests",
)


def test_migration_seed_is_idempotent_and_search_completes() -> None:
    assert database_health()[0]
    with get_session_factory()() as session:
        seed_all(session)
        seed_all(session)
        assert (
            session.scalar(
                select(func.count(Trademark.id)).where(Trademark.source_record_id.like("DEMO-%"))
            )
            == 60
        )

        case = CaseRecord(
            trademark_name="MarkLens",
            business_description="商标检索与风险分析软件服务",
            nice_classes=[9, 42],
            facts_snapshot={"trademark_name": "MarkLens", "nice_classes": [9, 42]},
        )
        session.add(case)
        session.flush()
        search = SearchRecord(
            case_id=case.id,
            query_snapshot=case.facts_snapshot,
            config_version="heuristic-v1",
            top_k=10,
        )
        session.add(search)
        session.commit()
        run = create_agent_run(session, "search", "req_ci", "search", search.id)

    execute_agent(run.id, build_search_operation(search.id))

    with get_session_factory()() as session:
        completed = session.get(AgentRun, run.id)
        assert completed is not None and completed.status == "completed"
        assert (
            session.scalar(select(func.count(SearchHit.id)).where(SearchHit.search_id == search.id))
            == 10
        )
