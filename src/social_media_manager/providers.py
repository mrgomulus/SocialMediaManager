from __future__ import annotations

from abc import ABC, abstractmethod
from random import random

from .models import Account, Post, Provider, PublishResult


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
        }

    def get(self, provider: Provider) -> BaseProviderClient:
        client = self._registry.get(provider)
        if client is None:
            raise ValueError(f"No provider client registered for: {provider}")
        return client
