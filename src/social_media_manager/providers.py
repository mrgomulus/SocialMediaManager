from __future__ import annotations

from abc import ABC, abstractmethod
from random import random
from uuid import uuid4

from .models import Account, Post, Provider, PublishResult, VideoGenerationJob, VideoGenerationResult


class BaseProviderClient(ABC):
    @abstractmethod
    def publish_post(self, account: Account, post: Post) -> PublishResult:
        raise NotImplementedError


class StableDemoProvider(BaseProviderClient):
    def publish_post(self, account: Account, post: Post) -> PublishResult:
        post_id = f"{account.provider.value}-{post.id.hex[:8]}"
        return PublishResult(success=True, provider_post_id=post_id)


class FlakyDemoProvider(BaseProviderClient):
    def __init__(self, failure_rate: float = 0.35) -> None:
        if not 0 <= failure_rate <= 1:
            raise ValueError("failure_rate must be between 0 and 1")
        self.failure_rate = failure_rate

    def publish_post(self, account: Account, post: Post) -> PublishResult:
        if random() < self.failure_rate:
            return PublishResult(success=False, error_message="Rate limit reached")
        post_id = f"flaky-{post.id.hex[:8]}"
        return PublishResult(success=True, provider_post_id=post_id)


class ProviderRegistry:
    def __init__(self) -> None:
        self._registry: dict[Provider, BaseProviderClient] = {
            Provider.POSTIZ_INSPIRED: StableDemoProvider(),
            Provider.MIXPOST_INSPIRED: FlakyDemoProvider(),
            Provider.GENERIC: StableDemoProvider(),
            Provider.YOUTUBE: StableDemoProvider(),
            Provider.TIKTOK: StableDemoProvider(),
            Provider.INSTAGRAM_REELS: StableDemoProvider(),
            Provider.TWITTER: StableDemoProvider(),
            Provider.FACEBOOK: StableDemoProvider(),
            Provider.LINKEDIN: StableDemoProvider(),
        }

    def get(self, provider: Provider) -> BaseProviderClient:
        client = self._registry.get(provider)
        if client is None:
            raise ValueError(f"No provider client registered for: {provider}")
        return client


# ---------------------------------------------------------------------------
# AI Video Generation provider infrastructure
# ---------------------------------------------------------------------------


class BaseVideoGenerationClient(ABC):
    """Abstract interface for external AI video generation services."""

    @abstractmethod
    def create_video(self, job: VideoGenerationJob) -> VideoGenerationResult:
        """Submit a video generation request and return an initial result."""
        raise NotImplementedError

    @abstractmethod
    def check_status(self, provider_job_id: str) -> VideoGenerationResult:
        """Poll the status of an existing generation job."""
        raise NotImplementedError


class GenericAIVideoClient(BaseVideoGenerationClient):
    """Stub implementation that immediately marks jobs as completed.

    Replace (or subclass) this with a real HTTP client that calls an AI video
    generation API such as RunwayML, Pika Labs, or Synthesia.
    """

    def create_video(self, job: VideoGenerationJob) -> VideoGenerationResult:
        provider_job_id = f"aivideo-{job.id.hex[:8]}"
        video_url = f"https://cdn.example.com/videos/{job.id.hex}.mp4"
        return VideoGenerationResult(
            success=True,
            provider_job_id=provider_job_id,
            video_url=video_url,
            is_complete=True,
        )

    def check_status(self, provider_job_id: str) -> VideoGenerationResult:
        video_url = f"https://cdn.example.com/videos/{provider_job_id}.mp4"
        return VideoGenerationResult(
            success=True,
            provider_job_id=provider_job_id,
            video_url=video_url,
            is_complete=True,
        )


class VideoGenerationProviderRegistry:
    _DEFAULT = "generic"

    def __init__(self) -> None:
        self._registry: dict[str, BaseVideoGenerationClient] = {
            self._DEFAULT: GenericAIVideoClient(),
        }

    def register(self, name: str, client: BaseVideoGenerationClient) -> None:
        """Register a custom AI video generation provider under *name*."""
        self._registry[name] = client

    def get(self, name: str = _DEFAULT) -> BaseVideoGenerationClient:
        client = self._registry.get(name)
        if client is None:
            raise ValueError(f"No video generation client registered for: {name}")
        return client
