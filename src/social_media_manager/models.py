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
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM_REELS = "instagram_reels"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"


class VideoGenerationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PostStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    REJECTED = "rejected"
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
    labels: list[str] = field(default_factory=list)
    media_urls: list[str] = field(default_factory=list)
    first_comment: Optional[str] = None
    review_comment: Optional[str] = None


@dataclass(slots=True)
class ContentTemplate:
    name: str
    body: str
    default_variables: dict[str, str] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class HashtagGroup:
    name: str
    hashtags: list[str]
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(slots=True)
class PostingTimeSlot:
    account_id: UUID
    weekday: int
    hour: int
    minute: int = 0
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class PublishResult:
    success: bool
    provider_post_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(slots=True)
class VideoGenerationResult:
    success: bool
    provider_job_id: Optional[str] = None
    video_url: Optional[str] = None
    error_message: Optional[str] = None
    is_complete: bool = False


@dataclass(slots=True)
class VideoGenerationJob:
    prompt: str
    account_ids: list[UUID]
    post_content: str
    id: UUID = field(default_factory=uuid4)
    status: VideoGenerationStatus = VideoGenerationStatus.PENDING
    video_url: Optional[str] = None
    provider_job_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    scheduled_publish_at: Optional[datetime] = None
    labels: list[str] = field(default_factory=list)
    published_post_ids: list[UUID] = field(default_factory=list)
