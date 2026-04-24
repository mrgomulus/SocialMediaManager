"""Tests for AI video generation and multi-channel social media support."""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from social_media_manager.models import (
    PostStatus,
    Provider,
    VideoGenerationStatus,
)
from social_media_manager.providers import (
    BaseVideoGenerationClient,
    GenericAIVideoClient,
    ProviderRegistry,
    VideoGenerationProviderRegistry,
    VideoGenerationResult,
)
from social_media_manager.repositories import (
    InMemoryAccountRepository,
    InMemoryPostRepository,
    InMemoryVideoJobRepository,
)
from social_media_manager.services import (
    AccountService,
    PostService,
    VideoGenerationService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _account_service():
    return AccountService(InMemoryAccountRepository())


def _make_accounts(providers):
    repo = InMemoryAccountRepository()
    svc = AccountService(repo)
    accounts = []
    for i, provider in enumerate(providers):
        acc = svc.connect_account(
            name=f"Channel-{i}",
            provider=provider,
            external_account_id=f"ext-{i}",
            access_token=f"token-{i}",
        )
        accounts.append(acc)
    return accounts


def _video_service(post_service=None):
    if post_service is None:
        post_service = PostService(InMemoryPostRepository())
    return VideoGenerationService(
        job_repo=InMemoryVideoJobRepository(),
        post_service=post_service,
        video_provider_registry=VideoGenerationProviderRegistry(),
    )


# ---------------------------------------------------------------------------
# Provider enum – new social media platforms are registered
# ---------------------------------------------------------------------------


def test_provider_enum_includes_real_platforms():
    platforms = {p.value for p in Provider}
    assert "youtube" in platforms
    assert "tiktok" in platforms
    assert "instagram_reels" in platforms
    assert "twitter" in platforms
    assert "facebook" in platforms
    assert "linkedin" in platforms


def test_provider_registry_has_all_platforms():
    registry = ProviderRegistry()
    for provider in Provider:
        client = registry.get(provider)
        assert client is not None


def test_connect_multiple_social_media_channels():
    providers = [
        Provider.YOUTUBE,
        Provider.TIKTOK,
        Provider.INSTAGRAM_REELS,
        Provider.TWITTER,
        Provider.FACEBOOK,
        Provider.LINKEDIN,
    ]
    accounts = _make_accounts(providers)
    assert len(accounts) == len(providers)
    provider_values = [a.provider for a in accounts]
    assert Provider.YOUTUBE in provider_values
    assert Provider.TIKTOK in provider_values


# ---------------------------------------------------------------------------
# VideoGenerationProviderRegistry
# ---------------------------------------------------------------------------


def test_video_provider_registry_returns_generic_by_default():
    registry = VideoGenerationProviderRegistry()
    client = registry.get()
    assert isinstance(client, GenericAIVideoClient)


def test_video_provider_registry_custom_registration():
    class StubClient(BaseVideoGenerationClient):
        def create_video(self, job):
            return VideoGenerationResult(success=True, provider_job_id="stub-1", video_url="https://stub.example.com/v.mp4", is_complete=True)

        def check_status(self, provider_job_id):
            return VideoGenerationResult(success=True, provider_job_id=provider_job_id, video_url="https://stub.example.com/v.mp4", is_complete=True)

    registry = VideoGenerationProviderRegistry()
    registry.register("stub", StubClient())
    assert isinstance(registry.get("stub"), StubClient)


def test_video_provider_registry_missing_raises():
    registry = VideoGenerationProviderRegistry()
    with pytest.raises(ValueError, match="No video generation client registered for"):
        registry.get("nonexistent")


# ---------------------------------------------------------------------------
# VideoGenerationService – create_job validation
# ---------------------------------------------------------------------------


def test_create_video_job_success():
    svc = _video_service()
    accounts = _make_accounts([Provider.YOUTUBE, Provider.TIKTOK])
    account_ids = [a.id for a in accounts]

    job = svc.create_job(
        prompt="A sunset over mountain peaks",
        account_ids=account_ids,
        post_content="Beautiful sunset timelapse #nature",
        labels=["nature", "timelapse"],
    )

    assert job.id is not None
    assert job.status == VideoGenerationStatus.PENDING
    assert job.prompt == "A sunset over mountain peaks"
    assert len(job.account_ids) == 2
    assert job.labels == ["nature", "timelapse"]
    assert job.video_url is None
    assert job.published_post_ids == []


def test_create_video_job_deduplicates_account_ids():
    svc = _video_service()
    accounts = _make_accounts([Provider.YOUTUBE])
    dup_ids = [accounts[0].id, accounts[0].id, accounts[0].id]

    job = svc.create_job(
        prompt="My video",
        account_ids=dup_ids,
        post_content="Post text",
    )
    assert len(job.account_ids) == 1


def test_create_video_job_empty_prompt_raises():
    svc = _video_service()
    accounts = _make_accounts([Provider.YOUTUBE])
    with pytest.raises(ValueError, match="Prompt must not be empty"):
        svc.create_job(prompt="  ", account_ids=[accounts[0].id], post_content="Caption")


def test_create_video_job_empty_content_raises():
    svc = _video_service()
    accounts = _make_accounts([Provider.YOUTUBE])
    with pytest.raises(ValueError, match="Post content must not be empty"):
        svc.create_job(prompt="Some prompt", account_ids=[accounts[0].id], post_content="  ")


def test_create_video_job_no_accounts_raises():
    svc = _video_service()
    with pytest.raises(ValueError, match="At least one account_id is required"):
        svc.create_job(prompt="Some prompt", account_ids=[], post_content="Caption")


def test_create_video_job_content_too_long_raises():
    svc = _video_service()
    accounts = _make_accounts([Provider.YOUTUBE])
    long_content = "x" * 281
    with pytest.raises(ValueError, match="Post content must be"):
        svc.create_job(prompt="Prompt", account_ids=[accounts[0].id], post_content=long_content)


# ---------------------------------------------------------------------------
# VideoGenerationService – process_pending_jobs
# ---------------------------------------------------------------------------


def test_process_pending_jobs_marks_completed():
    svc = _video_service()
    accounts = _make_accounts([Provider.YOUTUBE])
    job = svc.create_job(
        prompt="Ocean waves",
        account_ids=[accounts[0].id],
        post_content="Waves caption",
    )
    assert job.status == VideoGenerationStatus.PENDING

    now = datetime.utcnow()
    processed = svc.process_pending_jobs(now)

    assert len(processed) == 1
    assert processed[0].status == VideoGenerationStatus.COMPLETED
    assert processed[0].video_url is not None
    assert processed[0].completed_at == now


def test_process_pending_jobs_with_processing_provider():
    """Verify PROCESSING state when provider signals job is not yet complete."""

    class SlowVideoClient(BaseVideoGenerationClient):
        def create_video(self, job):
            return VideoGenerationResult(success=True, provider_job_id="slow-1", is_complete=False)

        def check_status(self, provider_job_id):
            return VideoGenerationResult(success=True, provider_job_id=provider_job_id, video_url="https://done.example.com/v.mp4", is_complete=True)

    registry = VideoGenerationProviderRegistry()
    registry.register("slow", SlowVideoClient())
    post_svc = PostService(InMemoryPostRepository())
    svc = VideoGenerationService(
        job_repo=InMemoryVideoJobRepository(),
        post_service=post_svc,
        video_provider_registry=registry,
        video_provider_name="slow",
    )

    accounts = _make_accounts([Provider.TIKTOK])
    svc.create_job(prompt="Waterfall", account_ids=[accounts[0].id], post_content="Falls caption")

    now = datetime.utcnow()
    submitted = svc.process_pending_jobs(now)
    assert submitted[0].status == VideoGenerationStatus.PROCESSING

    # Now poll
    polled = svc.poll_processing_jobs(now)
    assert len(polled) == 1
    assert polled[0].status == VideoGenerationStatus.COMPLETED
    assert polled[0].video_url == "https://done.example.com/v.mp4"


def test_process_pending_jobs_failure():
    class FailingVideoClient(BaseVideoGenerationClient):
        def create_video(self, job):
            return VideoGenerationResult(success=False, error_message="API quota exceeded")

        def check_status(self, provider_job_id):
            return VideoGenerationResult(success=False, error_message="not started")

    registry = VideoGenerationProviderRegistry()
    registry.register("failing", FailingVideoClient())
    post_svc = PostService(InMemoryPostRepository())
    svc = VideoGenerationService(
        job_repo=InMemoryVideoJobRepository(),
        post_service=post_svc,
        video_provider_registry=registry,
        video_provider_name="failing",
    )

    accounts = _make_accounts([Provider.INSTAGRAM_REELS])
    svc.create_job(prompt="Forest", account_ids=[accounts[0].id], post_content="Forest caption")

    now = datetime.utcnow()
    processed = svc.process_pending_jobs(now)
    assert processed[0].status == VideoGenerationStatus.FAILED
    assert "quota" in processed[0].error_message


# ---------------------------------------------------------------------------
# VideoGenerationService – auto_publish_completed_jobs
# ---------------------------------------------------------------------------


def test_auto_publish_creates_posts_for_all_target_accounts():
    post_repo = InMemoryPostRepository()
    post_svc = PostService(post_repo)
    svc = VideoGenerationService(
        job_repo=InMemoryVideoJobRepository(),
        post_service=post_svc,
        video_provider_registry=VideoGenerationProviderRegistry(),
    )

    accounts = _make_accounts([Provider.YOUTUBE, Provider.TIKTOK, Provider.TWITTER])
    account_ids = [a.id for a in accounts]

    job = svc.create_job(
        prompt="City skyline at night",
        account_ids=account_ids,
        post_content="Stunning city lights #cityscape",
        labels=["city", "night"],
    )

    now = datetime.utcnow()
    svc.process_pending_jobs(now)

    published_posts = svc.auto_publish_completed_jobs(now)
    assert len(published_posts) == 3

    for post in published_posts:
        assert post.status == PostStatus.SCHEDULED
        assert any(url.endswith(".mp4") for url in post.media_urls)
        assert post.labels == ["city", "night"]

    updated_job = svc.get_job(job.id)
    assert len(updated_job.published_post_ids) == 3


def test_auto_publish_respects_scheduled_publish_at():
    post_svc = PostService(InMemoryPostRepository())
    svc = VideoGenerationService(
        job_repo=InMemoryVideoJobRepository(),
        post_service=post_svc,
        video_provider_registry=VideoGenerationProviderRegistry(),
    )

    accounts = _make_accounts([Provider.FACEBOOK])
    future_publish = datetime.utcnow() + timedelta(hours=2)

    svc.create_job(
        prompt="Product launch",
        account_ids=[accounts[0].id],
        post_content="Launching tomorrow!",
        scheduled_publish_at=future_publish,
    )

    now = datetime.utcnow()
    svc.process_pending_jobs(now)

    # Should NOT publish yet because scheduled_publish_at is in the future
    posts = svc.auto_publish_completed_jobs(now)
    assert len(posts) == 0

    # Should publish after the scheduled time
    posts = svc.auto_publish_completed_jobs(future_publish + timedelta(seconds=1))
    assert len(posts) == 1


def test_auto_publish_skips_already_published_jobs():
    post_svc = PostService(InMemoryPostRepository())
    svc = VideoGenerationService(
        job_repo=InMemoryVideoJobRepository(),
        post_service=post_svc,
        video_provider_registry=VideoGenerationProviderRegistry(),
    )

    accounts = _make_accounts([Provider.LINKEDIN])
    svc.create_job(
        prompt="Thought leadership",
        account_ids=[accounts[0].id],
        post_content="Professional content",
    )

    now = datetime.utcnow()
    svc.process_pending_jobs(now)

    first = svc.auto_publish_completed_jobs(now)
    assert len(first) == 1

    # Second call should not create duplicate posts
    second = svc.auto_publish_completed_jobs(now)
    assert len(second) == 0


# ---------------------------------------------------------------------------
# VideoGenerationService – list_jobs
# ---------------------------------------------------------------------------


def test_list_jobs_filtered_by_status():
    svc = _video_service()
    accounts = _make_accounts([Provider.YOUTUBE])
    svc.create_job(prompt="Job A", account_ids=[accounts[0].id], post_content="Content A")
    svc.create_job(prompt="Job B", account_ids=[accounts[0].id], post_content="Content B")

    now = datetime.utcnow()
    svc.process_pending_jobs(now)

    all_jobs = svc.list_jobs()
    assert len(all_jobs) == 2

    completed = svc.list_jobs(status=VideoGenerationStatus.COMPLETED)
    assert len(completed) == 2

    pending = svc.list_jobs(status=VideoGenerationStatus.PENDING)
    assert len(pending) == 0


def test_get_job_returns_none_for_unknown_id():
    svc = _video_service()
    assert svc.get_job(uuid4()) is None
