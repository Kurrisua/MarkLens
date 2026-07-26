from app.seed import _learning_items, _practice_items


def test_each_learning_topic_has_one_hundred_distinct_cards() -> None:
    for slug in ("trademark-basics", "similarity", "application-path"):
        items = _learning_items(slug)
        assert len(items) == 100
        assert len({title for title, _ in items}) == 100
        assert all(len(body) >= 100 for _, body in items)


def test_practice_library_has_one_hundred_distinct_questions() -> None:
    items = _practice_items()
    assert len(items) == 100
    assert len({str(item["title"]) for item in items}) == 100
