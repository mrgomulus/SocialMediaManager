from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from .models import Account, Post, PostStatus, Provider
from .providers import ProviderRegistry

MAX_RETRIES = 3
MAX_CONTENT_LENGTH = 280
BASE_RETRY_DELAY_SECONDS = 60


class AccountService:
    def __init__(self, repo) -> None:
        self.repo = repo

    def connect_account(
        self,
        *,
        name: str,
        provider: Provider,
        external_account_id: str,
        access_token: str,
    ) -> Account:
        account = Account(
            name=name,
            provider=provider,
            external_account_id=external_account_id,
            access_token=access_token,
        )
        return self.repo.add(account)


class PostService:
    def __init__(self, post_repo) -> None:
        self.post_repo = post_repo

    def create_draft_post(self, account_id, content: str, scheduled_at: datetime) -> Post:
        self._validate(content, scheduled_at)
        post = Post(account_id=account_id, content=content, scheduled_at=scheduled_at)
        return self.post_repo.add(post)

    def submit_for_review(self, post_id):
        post = self._require(post_id)
        if post.status != PostStatus.DRAFT:
            raise ValueError("Only draft posts can be submitted for review")
        return self.post_repo.update(replace(post, status=PostStatus.IN_REVIEW))

    def approve(self, post_id):
        post = self._require(post_id)
        if post.status != PostStatus.IN_REVIEW:
            raise ValueError("Only in-review posts can be approved")
        return self.post_repo.update(replace(post, status=PostStatus.APPROVED))

    def schedule(self, post_id):
        post = self._require(post_id)
        if post.status not in {PostStatus.DRAFT, PostStatus.APPROVED}:
            raise ValueError("Only draft/approved posts can be scheduled")
        return self.post_repo.update(replace(post, status=PostStatus.SCHEDULED))

    def create_scheduled_post(self, account_id, content: str, scheduled_at: datetime) -> Post:
        draft = self.create_draft_post(account_id, content, scheduled_at)
        return self.schedule(draft.id)

    def _validate(self, content: str, scheduled_at: datetime) -> None:
        if not content.strip():
            raise ValueError("Content must not be empty")
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(f"Content must be <= {MAX_CONTENT_LENGTH} characters")
        if scheduled_at <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")

    def _require(self, post_id):
        post = self.post_repo.get(post_id)
        if post is None:
            raise ValueError("Post not found")
        return post


class PublishingService:
    def __init__(
        self,
        account_repo,
        post_repo,
        provider_registry: ProviderRegistry,
    ) -> None:
        self.account_repo = account_repo
        self.post_repo = post_repo
        self.provider_registry = provider_registry

    def publish_due_posts(self, now: datetime) -> list[Post]:
        processed: list[Post] = []
        for post in self.post_repo.list_due(now):
            account = self.account_repo.get(post.account_id)
            if account is None:
                processed.append(self.post_repo.update(replace(post, status=PostStatus.FAILED, error_message="Account not found")))
                continue

            provider = self.provider_registry.get(account.provider)
            result = provider.publish_post(account, post)
            if result.success:
                updated = replace(
                    post,
                    status=PostStatus.PUBLISHED,
                    published_at=now,
                    provider_post_id=result.provider_post_id,
                    error_message=None,
                )
                processed.append(self.post_repo.update(updated))
                continue

            new_retry_count = post.retry_count + 1
            if new_retry_count >= MAX_RETRIES:
                failed = replace(
                    post,
                    status=PostStatus.FAILED,
                    retry_count=new_retry_count,
                    error_message=result.error_message,
                )
                processed.append(self.post_repo.update(failed))
            else:
                retry_delay = BASE_RETRY_DELAY_SECONDS * (2 ** (new_retry_count - 1))
                retried = replace(
                    post,
                    retry_count=new_retry_count,
                    error_message=result.error_message,
                    scheduled_at=now + timedelta(seconds=retry_delay),
                )
                processed.append(self.post_repo.update(retried))

        return processed


class AnalyticsService:
    def __init__(self, post_repo) -> None:
        self.post_repo = post_repo

    def summary(self) -> dict:
        posts = self.post_repo.list_all()
        total = len(posts)
        by_status: dict[str, int] = {}
        for post in posts:
            by_status[post.status.value] = by_status.get(post.status.value, 0) + 1

        success_rate = 0.0
        if total:
            success_rate = by_status.get(PostStatus.PUBLISHED.value, 0) / total

        return {
            "total_posts": total,
            "by_status": by_status,
            "publish_success_rate": round(success_rate, 3),
        }
