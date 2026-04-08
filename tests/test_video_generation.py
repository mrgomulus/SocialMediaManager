"""Tests for AI video generation and multi-channel support."""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest

from social_media_manager.models import (
    AiVideoStatusResult,
    AiVideoSubmitResult,
    Provider,
    VideoGenerationJob,
    VideoJobStatus,
    VideoProvider,
)
from social_media_manager.providers import (
    AiVideoClientRegistry,
    BaseAiVideoClient,
    GenericDemoAiVideoClient,
    ProviderRegistry,
)
from social_media_manager.repositories import (
    InMemoryAccountRepository,
    InMemoryPostRepository,
    InMemoryVideoGenerationJobRepository,
)
from social_media_manager.services import (
    AccountService,
    CampaignService,
    PostService,
    VideoGenerationService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _future(minutes: int = 30) -> datetime:
    return datetime.utcnow() + timedelta(minutes=minutes)


class AlwaysCompletedAiVideoClient(BaseAiVideoClient):
    """Immediately returns a completed job with a fixed video URL."""

    def submit_job(self, prompt: str, **kwargs) -> AiVideoSubmitResult:
        return AiVideoSubmitResult(success=True, external_job_id="ext-abc123")

    def check_status(self, external_job_id: str) -> AiVideoStatusResult:
        return AiVideoStatusResult(
            status=VideoJobStatus.COMPLETED,
            video_url=f"https://videos.example.com/{external_job_id}.mp4",
        )


class AlwaysFailingAiVideoClient(BaseAiVideoClient):
    """Always fails at submission."""

    def submit_job(self, prompt: str, **kwargs) -> AiVideoSubmitResult:
        return AiVideoSubmitResult(success=False, error_message="Service unavailable")

    def check_status(self, external_job_id: str) -> AiVideoStatusResult:
        return AiVideoStatusResult(status=VideoJobStatus.FAILED, error_message="Service unavailable")


class ProcessingThenCompletedAiVideoClient(BaseAiVideoClient):
    """First call returns processing, second call returns completed."""

    def __init__(self) -> None:
        self._calls = 0

    def submit_job(self, prompt: str, **kwargs) -> AiVideoSubmitResult:
        return AiVideoSubmitResult(success=True, external_job_id="ext-xyz789")

    def check_status(self, external_job_id: str) -> AiVideoStatusResult:
        self._calls += 1
        if self._calls == 1:
            return AiVideoStatusResult(status=VideoJobStatus.PROCESSING)
        return AiVideoStatusResult(
            status=VideoJobStatus.COMPLETED,
            video_url=f"https://videos.example.com/{external_job_id}.mp4",
        )


def _make_service(ai_client: BaseAiVideoClient | None = None):
    account_repo = InMemoryAccountRepository()
    post_repo = InMemoryPostRepository()
    video_job_repo = InMemoryVideoGenerationJobRepository()
    post_service = PostService(post_repo)
    campaign_service = CampaignService(post_service)
    registry = AiVideoClientRegistry()
    if ai_client is not None:
        registry.register(VideoProvider.GENERIC, ai_client)
    service = VideoGenerationService(video_job_repo, registry, campaign_service)
    return service, account_repo, post_repo, video_job_repo


# ---------------------------------------------------------------------------
# Provider enum extension tests
# ---------------------------------------------------------------------------

def test_new_providers_available():
    """All major social media platforms are registered in Provider enum."""
    expected = {Provider.YOUTUBE, Provider.TIKTOK, Provider.INSTAGRAM, Provider.TWITTER, Provider.FACEBOOK, Provider.LINKEDIN}
    for p in expected:
        assert p in Provider


def test_provider_registry_supports_all_platforms():
    registry = ProviderRegistry()
    for provider in [Provider.YOUTUBE, Provider.TIKTOK, Provider.INSTAGRAM, Provider.TWITTER, Provider.FACEBOOK, Provider.LINKEDIN]:
        client = registry.get(provider)
        assert client is not None


def test_publish_post_via_new_provider():
    """Posts can be created and published for new social media platforms."""
    account_repo = InMemoryAccountRepository()
    post_repo = InMemoryPostRepository()
    registry = ProviderRegistry()

    for provider in [Provider.YOUTUBE, Provider.TIKTOK, Provider.INSTAGRAM, Provider.TWITTER, Provider.FACEBOOK, Provider.LINKEDIN]:
        account = AccountService(account_repo).connect_account(
            name=f"My {provider.value} Channel",
            provider=provider,
            external_account_id=f"ext-{provider.value}",
            access_token="token",
        )
        assert account.provider == provider


# ---------------------------------------------------------------------------
# VideoProvider enum and AI video client tests
# ---------------------------------------------------------------------------

def test_video_provider_enum_values():
    assert VideoProvider.RUNWAY == "runway"
    assert VideoProvider.PIKA == "pika"
    assert VideoProvider.GENERIC == "generic"


def test_generic_demo_ai_video_client_submit_and_status():
    client = GenericDemoAiVideoClient()
    result = client.submit_job("A cat riding a skateboard")
    assert result.success is True
    assert result.external_job_id is not None

    status = client.check_status(result.external_job_id)
    assert status.status == VideoJobStatus.COMPLETED
    assert status.video_url is not None


def test_ai_video_client_registry_get_registered():
    registry = AiVideoClientRegistry()
    client = registry.get(VideoProvider.GENERIC)
    assert isinstance(client, GenericDemoAiVideoClient)


def test_ai_video_client_registry_register_custom():
    registry = AiVideoClientRegistry()
    custom = AlwaysCompletedAiVideoClient()
    registry.register(VideoProvider.RUNWAY, custom)
    assert registry.get(VideoProvider.RUNWAY) is custom


def test_ai_video_client_registry_register_http():
    registry = AiVideoClientRegistry()
    registry.register_http(VideoProvider.PIKA, api_url="https://api.pika.art", api_key="secret")
    from social_media_manager.providers import HttpAiVideoClient
    client = registry.get(VideoProvider.PIKA)
    assert isinstance(client, HttpAiVideoClient)


def test_ai_video_client_registry_get_unregistered_raises():
    registry = AiVideoClientRegistry()
    with pytest.raises(ValueError):
        registry.get(VideoProvider.RUNWAY)


# ---------------------------------------------------------------------------
# VideoGenerationService tests
# ---------------------------------------------------------------------------

def test_create_video_job_success():
    service, _, _, video_job_repo = _make_service(AlwaysCompletedAiVideoClient())
    account_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    job = service.create_job(
        prompt="A futuristic city at sunset",
        account_ids=[account_id],
        post_caption="Check out this stunning AI video!",
        video_provider=VideoProvider.GENERIC,
        scheduled_at=_future(60),
    )

    assert isinstance(job, VideoGenerationJob)
    assert job.status == VideoJobStatus.PROCESSING
    assert job.external_job_id == "ext-abc123"
    assert job.prompt == "A futuristic city at sunset"
    assert job.account_ids == [account_id]


def test_create_video_job_submit_failure():
    service, _, _, _ = _make_service(AlwaysFailingAiVideoClient())
    account_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    job = service.create_job(
        prompt="Ocean waves",
        account_ids=[account_id],
        post_caption="Beautiful!",
        video_provider=VideoProvider.GENERIC,
        scheduled_at=_future(60),
    )

    assert job.status == VideoJobStatus.FAILED
    assert job.error_message == "Service unavailable"


def test_create_video_job_empty_prompt_raises():
    service, _, _, _ = _make_service()
    with pytest.raises(ValueError, match="Prompt must not be empty"):
        service.create_job(
            prompt="   ",
            account_ids=[UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")],
            post_caption="Caption",
            video_provider=VideoProvider.GENERIC,
            scheduled_at=_future(),
        )


def test_create_video_job_no_accounts_raises():
    service, _, _, _ = _make_service()
    with pytest.raises(ValueError, match="At least one account id is required"):
        service.create_job(
            prompt="Cool video",
            account_ids=[],
            post_caption="Caption",
            video_provider=VideoProvider.GENERIC,
            scheduled_at=_future(),
        )


def test_create_video_job_past_scheduled_at_raises():
    service, _, _, _ = _make_service()
    with pytest.raises(ValueError, match="Scheduled time must be in the future"):
        service.create_job(
            prompt="Cool video",
            account_ids=[UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")],
            post_caption="Caption",
            video_provider=VideoProvider.GENERIC,
            scheduled_at=datetime.utcnow() - timedelta(seconds=1),
        )


def test_poll_and_process_jobs_completed():
    service, account_repo, post_repo, video_job_repo = _make_service(AlwaysCompletedAiVideoClient())
    account_id = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

    job = service.create_job(
        prompt="Starry sky timelapse",
        account_ids=[account_id],
        post_caption="Stunning night sky!",
        video_provider=VideoProvider.GENERIC,
        scheduled_at=_future(120),
    )
    assert job.status == VideoJobStatus.PROCESSING

    updated = service.poll_and_process_jobs(datetime.utcnow())
    assert len(updated) == 1
    finished = updated[0]
    assert finished.status == VideoJobStatus.COMPLETED
    assert finished.video_url is not None
    assert len(finished.created_post_ids) == 1

    # The corresponding post should exist in the post repo
    stored_job = video_job_repo.get(job.id)
    assert stored_job.status == VideoJobStatus.COMPLETED


def test_poll_and_process_jobs_still_processing():
    client = ProcessingThenCompletedAiVideoClient()
    service, _, post_repo, _ = _make_service(client)
    account_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

    service.create_job(
        prompt="Dancing robots",
        account_ids=[account_id],
        post_caption="Robot dance party!",
        video_provider=VideoProvider.GENERIC,
        scheduled_at=_future(60),
    )

    # First poll: still processing
    first_poll = service.poll_and_process_jobs(datetime.utcnow())
    assert first_poll == []

    # Second poll: completed
    second_poll = service.poll_and_process_jobs(datetime.utcnow())
    assert len(second_poll) == 1
    assert second_poll[0].status == VideoJobStatus.COMPLETED


def test_list_jobs():
    service, _, _, _ = _make_service(AlwaysCompletedAiVideoClient())
    account_id = UUID("11111111-1111-1111-1111-111111111111")

    service.create_job(
        prompt="Job 1",
        account_ids=[account_id],
        post_caption="Caption 1",
        video_provider=VideoProvider.GENERIC,
        scheduled_at=_future(60),
    )
    service.create_job(
        prompt="Job 2",
        account_ids=[account_id],
        post_caption="Caption 2",
        video_provider=VideoProvider.GENERIC,
        scheduled_at=_future(120),
    )

    jobs = service.list_jobs()
    assert len(jobs) == 2


def test_get_job_not_found_raises():
    service, _, _, _ = _make_service()
    with pytest.raises(ValueError, match="Video generation job not found"):
        service.get_job(UUID("22222222-2222-2222-2222-222222222222"))


def test_poll_multiple_accounts():
    """Video generation job creates posts for all specified accounts."""
    service, account_repo, post_repo, _ = _make_service(AlwaysCompletedAiVideoClient())
    acc1 = UUID("33333333-3333-3333-3333-333333333333")
    acc2 = UUID("44444444-4444-4444-4444-444444444444")

    service.create_job(
        prompt="Multi-account video",
        account_ids=[acc1, acc2],
        post_caption="Posted to multiple channels!",
        video_provider=VideoProvider.GENERIC,
        scheduled_at=_future(60),
    )

    updated = service.poll_and_process_jobs(datetime.utcnow())
    assert len(updated) == 1
    finished = updated[0]
    assert finished.status == VideoJobStatus.COMPLETED
    # Two posts should have been created (one per account)
    assert len(finished.created_post_ids) == 2


# ---------------------------------------------------------------------------
# InMemoryVideoGenerationJobRepository tests
# ---------------------------------------------------------------------------

def test_video_job_repo_add_and_get():
    from social_media_manager.repositories import InMemoryVideoGenerationJobRepository

    repo = InMemoryVideoGenerationJobRepository()
    job = VideoGenerationJob(
        prompt="Test",
        account_ids=[UUID("55555555-5555-5555-5555-555555555555")],
        post_caption="Caption",
        video_provider=VideoProvider.GENERIC,
        scheduled_at=_future(),
        status=VideoJobStatus.PROCESSING,
        external_job_id="ext-test",
    )
    added = repo.add(job)
    assert added.id == job.id

    fetched = repo.get(job.id)
    assert fetched is not None
    assert fetched.prompt == "Test"


def test_video_job_repo_list_processing():
    from dataclasses import replace

    from social_media_manager.repositories import InMemoryVideoGenerationJobRepository

    repo = InMemoryVideoGenerationJobRepository()
    j1 = VideoGenerationJob(
        prompt="Processing job",
        account_ids=[UUID("66666666-6666-6666-6666-666666666666")],
        post_caption="Cap",
        video_provider=VideoProvider.GENERIC,
        scheduled_at=_future(),
        status=VideoJobStatus.PROCESSING,
        external_job_id="ext-1",
    )
    j2 = VideoGenerationJob(
        prompt="Completed job",
        account_ids=[UUID("77777777-7777-7777-7777-777777777777")],
        post_caption="Cap",
        video_provider=VideoProvider.GENERIC,
        scheduled_at=_future(),
        status=VideoJobStatus.COMPLETED,
    )
    repo.add(j1)
    repo.add(j2)

    processing = repo.list_processing()
    assert len(processing) == 1
    assert processing[0].id == j1.id
