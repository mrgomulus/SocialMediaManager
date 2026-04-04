from datetime import datetime, timedelta

import pytest

from social_media_manager.models import PostStatus, Provider
from social_media_manager.providers import BaseProviderClient, ProviderRegistry
from social_media_manager.repositories import InMemoryAccountRepository, InMemoryPostRepository
from social_media_manager.services import (
    AccountService,
    AnalyticsService,
    PostService,
    PublishingService,
)


class AlwaysFailProvider(BaseProviderClient):
    def publish_post(self, account, post):
        from social_media_manager.models import PublishResult

        return PublishResult(success=False, error_message="temporary failure")


class FailingRegistry(ProviderRegistry):
    def __init__(self):
        super().__init__()
        self._registry[Provider.POSTIZ_INSPIRED] = AlwaysFailProvider()


def test_create_scheduled_post_requires_future_time():
    repo = InMemoryPostRepository()
    service = PostService(repo)

    with pytest.raises(ValueError):
        service.create_scheduled_post(
            account_id="x",
            content="Test",
            scheduled_at=datetime.utcnow() - timedelta(seconds=1),
        )


def test_review_workflow_transition():
    posts = InMemoryPostRepository()
    service = PostService(posts)

    post = service.create_draft_post(
        account_id="acc",
        content="Workflow",
        scheduled_at=datetime.utcnow() + timedelta(minutes=5),
    )
    assert post.status == PostStatus.DRAFT

    review = service.submit_for_review(post.id)
    assert review.status == PostStatus.IN_REVIEW

    approved = service.approve(post.id)
    assert approved.status == PostStatus.APPROVED

    scheduled = service.schedule(post.id)
    assert scheduled.status == PostStatus.SCHEDULED


def test_publish_due_posts_success_flow():
    account_repo = InMemoryAccountRepository()
    post_repo = InMemoryPostRepository()
    providers = ProviderRegistry()

    account = AccountService(account_repo).connect_account(
        name="A",
        provider=Provider.GENERIC,
        external_account_id="e1",
        access_token="token",
    )

    post = PostService(post_repo).create_scheduled_post(
        account.id,
        "Content",
        datetime.utcnow() + timedelta(seconds=1),
    )

    service = PublishingService(account_repo, post_repo, providers)
    updated = service.publish_due_posts(datetime.utcnow() + timedelta(seconds=5))

    assert len(updated) == 1
    assert updated[0].id == post.id
    assert updated[0].status == PostStatus.PUBLISHED
    assert updated[0].provider_post_id is not None


def test_publish_retries_with_backoff_then_fails():
    account_repo = InMemoryAccountRepository()
    post_repo = InMemoryPostRepository()
    providers = FailingRegistry()

    account = AccountService(account_repo).connect_account(
        name="A",
        provider=Provider.POSTIZ_INSPIRED,
        external_account_id="e1",
        access_token="token",
    )

    PostService(post_repo).create_scheduled_post(
        account.id,
        "Content",
        datetime.utcnow() + timedelta(seconds=1),
    )

    service = PublishingService(account_repo, post_repo, providers)

    t0 = datetime.utcnow() + timedelta(seconds=5)
    first = service.publish_due_posts(t0)[0]
    assert first.retry_count == 1

    none_due = service.publish_due_posts(t0 + timedelta(seconds=30))
    assert none_due == []

    second = service.publish_due_posts(t0 + timedelta(seconds=65))[0]
    assert second.retry_count == 2

    third = service.publish_due_posts(t0 + timedelta(seconds=190))[0]
    assert third.status == PostStatus.FAILED
    assert third.retry_count == 3


def test_analytics_summary_counts_statuses():
    post_repo = InMemoryPostRepository()
    post_service = PostService(post_repo)

    scheduled = post_service.create_scheduled_post(
        account_id="a1",
        content="One",
        scheduled_at=datetime.utcnow() + timedelta(minutes=1),
    )
    post_service.create_draft_post(
        account_id="a1",
        content="Two",
        scheduled_at=datetime.utcnow() + timedelta(minutes=2),
    )

    scheduled.status = PostStatus.PUBLISHED
    post_repo.update(scheduled)

    summary = AnalyticsService(post_repo).summary()
    assert summary["total_posts"] == 2
    assert summary["by_status"]["published"] == 1
