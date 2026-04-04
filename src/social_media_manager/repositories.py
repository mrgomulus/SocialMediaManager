from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from .models import Account, Post, PostStatus


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
