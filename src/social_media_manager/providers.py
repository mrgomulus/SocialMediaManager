from __future__ import annotations

import json
from abc import ABC, abstractmethod
from random import random
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .models import (
    Account,
    AiVideoStatusResult,
    AiVideoSubmitResult,
    Post,
    Provider,
    PublishResult,
    VideoJobStatus,
    VideoProvider,
)


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
            Provider.INSTAGRAM: StableDemoProvider(),
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
# AI Video generation clients
# ---------------------------------------------------------------------------


class BaseAiVideoClient(ABC):
    @abstractmethod
    def submit_job(self, prompt: str, **kwargs: Any) -> AiVideoSubmitResult:
        raise NotImplementedError

    @abstractmethod
    def check_status(self, external_job_id: str) -> AiVideoStatusResult:
        raise NotImplementedError


class GenericDemoAiVideoClient(BaseAiVideoClient):
    """Demo client that immediately returns a completed job with a placeholder video URL."""

    def submit_job(self, prompt: str, **kwargs: Any) -> AiVideoSubmitResult:
        from uuid import uuid4

        job_id = f"demo-{uuid4().hex[:8]}"
        return AiVideoSubmitResult(success=True, external_job_id=job_id)

    def check_status(self, external_job_id: str) -> AiVideoStatusResult:
        return AiVideoStatusResult(
            status=VideoJobStatus.COMPLETED,
            video_url=f"https://example.com/videos/{external_job_id}.mp4",
        )


class HttpAiVideoClient(BaseAiVideoClient):
    """Client that calls an external HTTP API to generate AI videos.

    Expected API contract:
    - POST ``{api_url}/generate`` with JSON body ``{"prompt": "..."}``
      and ``Authorization: Bearer {api_key}`` header.
      Response: ``{"job_id": "<id>"}`` on success or ``{"error": "..."}`` on failure.
    - GET ``{api_url}/status/{job_id}`` with the same auth header.
      Response: ``{"status": "processing|completed|failed", "video_url": "...", "error": "..."}``
    """

    def __init__(self, api_url: str, api_key: str = "", timeout: int = 10) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def submit_job(self, prompt: str, **kwargs: Any) -> AiVideoSubmitResult:
        body = json.dumps({"prompt": prompt, **kwargs}).encode()
        req = Request(
            f"{self.api_url}/generate",
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
        except URLError as exc:
            return AiVideoSubmitResult(success=False, error_message=str(exc))
        except Exception as exc:  # noqa: BLE001
            return AiVideoSubmitResult(success=False, error_message=str(exc))

        if "error" in data:
            return AiVideoSubmitResult(success=False, error_message=data["error"])
        return AiVideoSubmitResult(success=True, external_job_id=data.get("job_id"))

    def check_status(self, external_job_id: str) -> AiVideoStatusResult:
        req = Request(
            f"{self.api_url}/status/{external_job_id}",
            headers=self._headers(),
            method="GET",
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
        except URLError as exc:
            return AiVideoStatusResult(status=VideoJobStatus.FAILED, error_message=str(exc))
        except Exception as exc:  # noqa: BLE001
            return AiVideoStatusResult(status=VideoJobStatus.FAILED, error_message=str(exc))

        raw_status = data.get("status", "")
        try:
            status = VideoJobStatus(raw_status)
        except ValueError:
            status = VideoJobStatus.PROCESSING

        return AiVideoStatusResult(
            status=status,
            video_url=data.get("video_url"),
            error_message=data.get("error"),
        )


class AiVideoClientRegistry:
    def __init__(self) -> None:
        self._registry: dict[VideoProvider, BaseAiVideoClient] = {
            VideoProvider.GENERIC: GenericDemoAiVideoClient(),
        }

    def register(self, provider: VideoProvider, client: BaseAiVideoClient) -> None:
        self._registry[provider] = client

    def register_http(self, provider: VideoProvider, api_url: str, api_key: str = "") -> None:
        self._registry[provider] = HttpAiVideoClient(api_url=api_url, api_key=api_key)

    def get(self, provider: VideoProvider) -> BaseAiVideoClient:
        client = self._registry.get(provider)
        if client is None:
            raise ValueError(f"No AI video client registered for: {provider}")
        return client
