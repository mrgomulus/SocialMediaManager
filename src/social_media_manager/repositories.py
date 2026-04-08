from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from .models import (
    Account,
    ContentTemplate,
    HashtagGroup,
    Post,
    PostStatus,
    PostingTimeSlot,
    VideoGenerationJob,
    VideoJobStatus,
)


class InMemoryAccountRepository:
    def __init__(self) -> None:
        self._items: Dict[UUID, Account] = {}

    def add(self, account: Account) -> Account:
        self._items[account.id] = account
        return account

    def get(self, account_id: UUID) -> Optional[Account]:
        return self._items.get(account_id)

    def list_all(self) -> List[Account]:
        return list(self._items.values())


class InMemoryPostRepository:
    def __init__(self) -> None:
        self._items: Dict[UUID, Post] = {}

    def add(self, post: Post) -> Post:
        self._items[post.id] = post
        return post

    def update(self, post: Post) -> Post:
        self._items[post.id] = post
        return post

    def get(self, post_id: UUID) -> Optional[Post]:
        return self._items.get(post_id)

    def list_all(self) -> List[Post]:
        return list(self._items.values())

    def list_due(self, now: datetime) -> List[Post]:
        due_posts = [
            p
            for p in self._items.values()
            if p.status == PostStatus.SCHEDULED and p.scheduled_at <= now
        ]
        return sorted(due_posts, key=lambda p: p.scheduled_at)

    def mark_failed(self, post: Post, error: str) -> Post:
        updated = replace(post, status=PostStatus.FAILED, error_message=error)
        self._items[updated.id] = updated
        return updated


class InMemoryTemplateRepository:
    def __init__(self) -> None:
        self._items: Dict[UUID, ContentTemplate] = {}

    def add(self, template: ContentTemplate) -> ContentTemplate:
        self._items[template.id] = template
        return template

    def update(self, template: ContentTemplate) -> ContentTemplate:
        self._items[template.id] = template
        return template

    def get(self, template_id: UUID) -> Optional[ContentTemplate]:
        return self._items.get(template_id)

    def list_all(self) -> List[ContentTemplate]:
        return list(self._items.values())


class InMemoryHashtagGroupRepository:
    def __init__(self) -> None:
        self._items: Dict[UUID, HashtagGroup] = {}

    def add(self, group: HashtagGroup) -> HashtagGroup:
        self._items[group.id] = group
        return group

    def get(self, group_id: UUID) -> Optional[HashtagGroup]:
        return self._items.get(group_id)

    def list_all(self) -> List[HashtagGroup]:
        return list(self._items.values())


class InMemoryPostingSlotRepository:
    def __init__(self) -> None:
        self._items: Dict[UUID, List[PostingTimeSlot]] = {}

    def replace_for_account(self, account_id: UUID, slots: List[PostingTimeSlot]) -> List[PostingTimeSlot]:
        self._items[account_id] = sorted(slots, key=lambda s: (s.weekday, s.hour, s.minute))
        return self._items[account_id]

    def list_for_account(self, account_id: UUID) -> List[PostingTimeSlot]:
        return list(self._items.get(account_id, []))


class InMemoryVideoGenerationJobRepository:
    def __init__(self) -> None:
        self._items: Dict[UUID, VideoGenerationJob] = {}

    def add(self, job: VideoGenerationJob) -> VideoGenerationJob:
        self._items[job.id] = job
        return job

    def update(self, job: VideoGenerationJob) -> VideoGenerationJob:
        self._items[job.id] = job
        return job

    def get(self, job_id: UUID) -> Optional[VideoGenerationJob]:
        return self._items.get(job_id)

    def list_all(self) -> List[VideoGenerationJob]:
        return list(self._items.values())

    def list_processing(self) -> List[VideoGenerationJob]:
        return [job for job in self._items.values() if job.status == VideoJobStatus.PROCESSING]
