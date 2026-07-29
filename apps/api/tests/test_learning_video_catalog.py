from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import LearningVideo
from app.seed import seed_product_content


def test_seeded_learning_video_catalog_has_more_than_one_hundred_real_bilibili_links() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_product_content(session)
            items = session.scalars(select(LearningVideo)).all()

        assert len(items) >= 105
        assert all(item.external_url.startswith("https://www.bilibili.com/video/BV") for item in items)
        assert len({item.external_url for item in items}) == len(items)
    finally:
        Base.metadata.drop_all(engine)
