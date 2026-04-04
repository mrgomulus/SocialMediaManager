from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class Provider(str, Enum):
    POSTIZ_INSPIRED = "postiz_inspired"
    MIXPOST_INSPIRED = "mixpost_inspired"
    GENERIC = "generic"


class PostStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass(slots=True)
class Account:
    name: str
    provider: Provider
    external_account_id: str
    access_token: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class Post:
    account_id: UUID
    content: str
    scheduled_at: datetime
    id: UUID = field(default_factory=uuid4)
    status: PostStatus = PostStatus.DRAFT
    published_at: Optional[datetime] = None
    provider_post_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass(slots=True)
class PublishResult:
    success: bool
    provider_post_id: Optional[str] = None
    error_message: Optional[str] = None
