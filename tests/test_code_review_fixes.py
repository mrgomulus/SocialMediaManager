from datetime import datetime, timedelta

import pytest

from social_media_manager.models import Post, PostStatus
from social_media_manager.providers import FlakyDemoProvider, ProviderRegistry
from social_media_manager.repositories import InMemoryPostRepository
from social_media_manager.scheduler import SchedulerWorker


class DummyPublisher:
    def publish_due_posts(self, now):
        return []


def test_flaky_provider_validates_failure_rate():
    with pytest.raises(ValueError):
        FlakyDemoProvider(failure_rate=1.5)


def test_provider_registry_missing_provider_error_message():
    registry = ProviderRegistry()
    registry._registry.clear()
    with pytest.raises(ValueError, match="No provider client registered"):
        registry.get("missing")  # type: ignore[arg-type]


def test_scheduler_validates_tick_and_ticks():
    with pytest.raises(ValueError):
        SchedulerWorker(DummyPublisher(), tick_seconds=0)

    worker = SchedulerWorker(DummyPublisher(), tick_seconds=10)
    with pytest.raises(ValueError):
        worker.simulate(start=datetime.utcnow(), ticks=-1)


def test_inmemory_due_posts_are_ordered_by_scheduled_at():
    repo = InMemoryPostRepository()
    now = datetime.utcnow()

    late = Post(account_id="a", content="late", scheduled_at=now + timedelta(seconds=20), status=PostStatus.SCHEDULED)
    early = Post(account_id="a", content="early", scheduled_at=now + timedelta(seconds=10), status=PostStatus.SCHEDULED)

    repo.add(late)
    repo.add(early)

    due = repo.list_due(now + timedelta(seconds=30))
    assert [p.content for p in due] == ["early", "late"]
