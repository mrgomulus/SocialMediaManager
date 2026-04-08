from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, time, timedelta
from uuid import UUID

from .models import (
    Account,
    ContentTemplate,
    HashtagGroup,
    Post,
    PostStatus,
    PostingTimeSlot,
    Provider,
    VideoGenerationJob,
    VideoJobStatus,
    VideoProvider,
)
from .providers import ProviderRegistry
from .providers import AiVideoClientRegistry

MAX_RETRIES = 3
MAX_CONTENT_LENGTH = 280
BASE_RETRY_DELAY_SECONDS = 60
TEMPLATE_VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


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

    def create_draft_post(
        self,
        account_id,
        content: str,
        scheduled_at: datetime,
        *,
        labels: list[str] | None = None,
        media_urls: list[str] | None = None,
        first_comment: str | None = None,
    ) -> Post:
        self._validate(content, scheduled_at)
        post = Post(
            account_id=account_id,
            content=content,
            scheduled_at=scheduled_at,
            labels=labels or [],
            media_urls=media_urls or [],
            first_comment=first_comment,
        )
        return self.post_repo.add(post)

    def submit_for_review(self, post_id):
        post = self._require(post_id)
        if post.status not in {PostStatus.DRAFT, PostStatus.REJECTED}:
            raise ValueError("Only draft/rejected posts can be submitted for review")
        return self.post_repo.update(replace(post, status=PostStatus.IN_REVIEW, review_comment=None))

    def approve(self, post_id):
        post = self._require(post_id)
        if post.status != PostStatus.IN_REVIEW:
            raise ValueError("Only in-review posts can be approved")
        return self.post_repo.update(replace(post, status=PostStatus.APPROVED, review_comment=None))

    def reject(self, post_id, reason: str):
        post = self._require(post_id)
        if post.status != PostStatus.IN_REVIEW:
            raise ValueError("Only in-review posts can be rejected")
        cleaned_reason = reason.strip()
        if not cleaned_reason:
            raise ValueError("Reject reason must not be empty")
        return self.post_repo.update(
            replace(
                post,
                status=PostStatus.REJECTED,
                review_comment=cleaned_reason,
            )
        )

    def schedule(self, post_id):
        post = self._require(post_id)
        if post.status not in {PostStatus.DRAFT, PostStatus.APPROVED, PostStatus.REJECTED}:
            raise ValueError("Only draft/approved/rejected posts can be scheduled")
        return self.post_repo.update(replace(post, status=PostStatus.SCHEDULED))

    def create_scheduled_post(
        self,
        account_id,
        content: str,
        scheduled_at: datetime,
        *,
        labels: list[str] | None = None,
        media_urls: list[str] | None = None,
        first_comment: str | None = None,
    ) -> Post:
        draft = self.create_draft_post(
            account_id,
            content,
            scheduled_at,
            labels=labels,
            media_urls=media_urls,
            first_comment=first_comment,
        )
        return self.schedule(draft.id)

    def update_draft_content(self, post_id, content: str) -> Post:
        post = self._require(post_id)
        if post.status not in {PostStatus.DRAFT, PostStatus.REJECTED, PostStatus.IN_REVIEW}:
            raise ValueError("Only draft/rejected/in-review posts can be edited")
        self._validate(content, post.scheduled_at)
        return self.post_repo.update(replace(post, content=content))

    def duplicate_as_draft(self, post_id, *, scheduled_at: datetime | None = None) -> Post:
        post = self._require(post_id)
        target_time = scheduled_at or (datetime.utcnow() + timedelta(minutes=15))
        self._validate(post.content, target_time)
        duplicate = Post(
            account_id=post.account_id,
            content=post.content,
            scheduled_at=target_time,
            labels=list(post.labels),
            media_urls=list(post.media_urls),
            first_comment=post.first_comment,
        )
        return self.post_repo.add(duplicate)

    def list_posts(self, *, account_id: UUID | None = None, status: PostStatus | None = None) -> list[Post]:
        posts = self.post_repo.list_all()
        if account_id is not None:
            posts = [post for post in posts if post.account_id == account_id]
        if status is not None:
            posts = [post for post in posts if post.status == status]
        return sorted(posts, key=lambda p: p.scheduled_at)

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


class TemplateService:
    def __init__(self, template_repo) -> None:
        self.template_repo = template_repo

    def create_template(
        self,
        *,
        name: str,
        body: str,
        default_variables: dict[str, str] | None = None,
    ) -> ContentTemplate:
        cleaned_name = name.strip()
        cleaned_body = body.strip()
        if not cleaned_name:
            raise ValueError("Template name must not be empty")
        if not cleaned_body:
            raise ValueError("Template body must not be empty")
        template = ContentTemplate(
            name=cleaned_name,
            body=cleaned_body,
            default_variables=default_variables or {},
        )
        return self.template_repo.add(template)

    def list_templates(self) -> list[ContentTemplate]:
        return sorted(self.template_repo.list_all(), key=lambda t: t.created_at)

    def render(self, template_id, variables: dict[str, str] | None = None) -> str:
        template = self.template_repo.get(template_id)
        if template is None:
            raise ValueError("Template not found")
        return self.render_inline(
            template.body,
            variables=variables,
            default_variables=template.default_variables,
        )

    def render_inline(
        self,
        template_body: str,
        *,
        variables: dict[str, str] | None = None,
        default_variables: dict[str, str] | None = None,
    ) -> str:
        merged_variables: dict[str, str] = {}
        for key, value in (default_variables or {}).items():
            merged_variables[str(key)] = str(value)
        for key, value in (variables or {}).items():
            merged_variables[str(key)] = str(value)

        rendered = template_body
        placeholders = set(TEMPLATE_VARIABLE_PATTERN.findall(template_body))
        missing = sorted(name for name in placeholders if name not in merged_variables)
        if missing:
            missing_list = ", ".join(missing)
            raise ValueError(f"Missing template variables: {missing_list}")

        for key, value in merged_variables.items():
            rendered = re.sub(r"\{\{\s*" + re.escape(key) + r"\s*\}\}", value, rendered)
        return rendered


class HashtagGroupService:
    def __init__(self, hashtag_group_repo) -> None:
        self.hashtag_group_repo = hashtag_group_repo

    def create_group(self, *, name: str, hashtags: list[str]) -> HashtagGroup:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Group name must not be empty")
        normalized = self._normalize_hashtags(hashtags)
        if not normalized:
            raise ValueError("At least one hashtag is required")
        group = HashtagGroup(name=cleaned_name, hashtags=normalized)
        return self.hashtag_group_repo.add(group)

    def list_groups(self) -> list[HashtagGroup]:
        return sorted(self.hashtag_group_repo.list_all(), key=lambda g: g.created_at)

    def compose_hashtag_suffix(self, group_ids: list[UUID]) -> str:
        collected: list[str] = []
        seen: set[str] = set()
        for group_id in group_ids:
            group = self.hashtag_group_repo.get(group_id)
            if group is None:
                raise ValueError(f"Hashtag group not found: {group_id}")
            for hashtag in group.hashtags:
                if hashtag not in seen:
                    seen.add(hashtag)
                    collected.append(hashtag)
        return " ".join(collected)

    def _normalize_hashtags(self, hashtags: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for hashtag in hashtags:
            token = hashtag.strip().lstrip("#").replace(" ", "")
            if not token:
                continue
            canonical = token.lower()
            if canonical in seen:
                continue
            seen.add(canonical)
            cleaned.append(f"#{token}")
        return cleaned


class QueuePlannerService:
    def __init__(self, posting_slot_repo) -> None:
        self.posting_slot_repo = posting_slot_repo

    def replace_slots(self, account_id, slots: list[dict]) -> list[PostingTimeSlot]:
        if not slots:
            raise ValueError("At least one slot is required")
        normalized: list[PostingTimeSlot] = []
        for slot in slots:
            weekday = int(slot["weekday"])
            hour = int(slot["hour"])
            minute = int(slot.get("minute", 0))
            self._validate_slot(weekday, hour, minute)
            normalized.append(
                PostingTimeSlot(
                    account_id=account_id,
                    weekday=weekday,
                    hour=hour,
                    minute=minute,
                )
            )
        return self.posting_slot_repo.replace_for_account(account_id, normalized)

    def list_slots(self, account_id) -> list[PostingTimeSlot]:
        return self.posting_slot_repo.list_for_account(account_id)

    def next_available_slot(self, account_id, *, from_time: datetime | None = None) -> datetime:
        now = from_time or datetime.utcnow()
        slots = self.posting_slot_repo.list_for_account(account_id)
        if not slots:
            raise ValueError("No posting time slots configured for account")

        candidates: list[datetime] = []
        for day_offset in range(0, 15):
            day = (now + timedelta(days=day_offset)).date()
            weekday = day.weekday()
            for slot in slots:
                if slot.weekday != weekday:
                    continue
                candidate = datetime.combine(day, time(hour=slot.hour, minute=slot.minute))
                if candidate > now:
                    candidates.append(candidate)
        if not candidates:
            raise ValueError("Could not calculate next available slot")
        return min(candidates)

    def _validate_slot(self, weekday: int, hour: int, minute: int) -> None:
        if weekday < 0 or weekday > 6:
            raise ValueError("weekday must be between 0 and 6")
        if hour < 0 or hour > 23:
            raise ValueError("hour must be between 0 and 23")
        if minute < 0 or minute > 59:
            raise ValueError("minute must be between 0 and 59")


class CampaignService:
    def __init__(self, post_service: PostService) -> None:
        self.post_service = post_service

    def create_campaign_posts(
        self,
        *,
        account_ids: list[UUID],
        content: str,
        scheduled_at: datetime,
        labels: list[str] | None = None,
        media_urls: list[str] | None = None,
        first_comment: str | None = None,
    ) -> list[Post]:
        unique_accounts = list(dict.fromkeys(account_ids))
        if not unique_accounts:
            raise ValueError("At least one account id is required")

        created: list[Post] = []
        for account_id in unique_accounts:
            post = self.post_service.create_scheduled_post(
                account_id=account_id,
                content=content,
                scheduled_at=scheduled_at,
                labels=labels,
                media_urls=media_urls,
                first_comment=first_comment,
            )
            created.append(post)
        return created


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
    def __init__(self, post_repo, account_repo=None) -> None:
        self.post_repo = post_repo
        self.account_repo = account_repo

    def summary(self) -> dict:
        now = datetime.utcnow()
        posts = self.post_repo.list_all()
        total = len(posts)
        by_status: dict[str, int] = {}
        for post in posts:
            by_status[post.status.value] = by_status.get(post.status.value, 0) + 1

        success_rate = 0.0
        if total:
            success_rate = by_status.get(PostStatus.PUBLISHED.value, 0) / total

        failed_posts = by_status.get(PostStatus.FAILED.value, 0)
        retry_total = sum(post.retry_count for post in posts)
        average_retry_count = (retry_total / total) if total else 0.0

        upcoming_cutoff = now + timedelta(hours=24)
        upcoming_posts_24h = sum(
            1
            for post in posts
            if post.status == PostStatus.SCHEDULED and now < post.scheduled_at <= upcoming_cutoff
        )

        by_provider: dict[str, int] = {}
        if self.account_repo is not None:
            for post in posts:
                account = self.account_repo.get(post.account_id)
                if account is None:
                    continue
                provider_key = account.provider.value
                by_provider[provider_key] = by_provider.get(provider_key, 0) + 1

        return {
            "total_posts": total,
            "by_status": by_status,
            "publish_success_rate": round(success_rate, 3),
            "failed_posts": failed_posts,
            "average_retry_count": round(average_retry_count, 3),
            "upcoming_posts_24h": upcoming_posts_24h,
            "by_provider": by_provider,
        }


class VideoGenerationService:
    """Orchestrates AI video generation and automatic upload to social media accounts."""

    MAX_CAPTION_LENGTH = 500

    def __init__(
        self,
        video_job_repo,
        ai_video_registry: AiVideoClientRegistry,
        campaign_service: CampaignService,
    ) -> None:
        self.video_job_repo = video_job_repo
        self.ai_video_registry = ai_video_registry
        self.campaign_service = campaign_service

    def create_job(
        self,
        *,
        prompt: str,
        account_ids: list[UUID],
        post_caption: str,
        video_provider: VideoProvider,
        scheduled_at: datetime,
    ) -> VideoGenerationJob:
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise ValueError("Prompt must not be empty")
        if not account_ids:
            raise ValueError("At least one account id is required")
        cleaned_caption = post_caption.strip()
        if not cleaned_caption:
            raise ValueError("Post caption must not be empty")
        if len(cleaned_caption) > self.MAX_CAPTION_LENGTH:
            raise ValueError(f"Post caption must be <= {self.MAX_CAPTION_LENGTH} characters")
        if scheduled_at <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")

        client = self.ai_video_registry.get(video_provider)
        result = client.submit_job(cleaned_prompt)

        if not result.success:
            job = VideoGenerationJob(
                prompt=cleaned_prompt,
                account_ids=list(account_ids),
                post_caption=cleaned_caption,
                video_provider=video_provider,
                scheduled_at=scheduled_at,
                status=VideoJobStatus.FAILED,
                error_message=result.error_message,
            )
        else:
            job = VideoGenerationJob(
                prompt=cleaned_prompt,
                account_ids=list(account_ids),
                post_caption=cleaned_caption,
                video_provider=video_provider,
                scheduled_at=scheduled_at,
                status=VideoJobStatus.PROCESSING,
                external_job_id=result.external_job_id,
            )
        return self.video_job_repo.add(job)

    def poll_and_process_jobs(self, now: datetime) -> list[VideoGenerationJob]:
        updated: list[VideoGenerationJob] = []
        for job in self.video_job_repo.list_processing():
            if job.external_job_id is None:
                continue
            client = self.ai_video_registry.get(job.video_provider)
            status_result = client.check_status(job.external_job_id)

            if status_result.status == VideoJobStatus.COMPLETED:
                media_urls = [status_result.video_url] if status_result.video_url else []
                posts = self.campaign_service.create_campaign_posts(
                    account_ids=job.account_ids,
                    content=job.post_caption,
                    scheduled_at=job.scheduled_at,
                    media_urls=media_urls,
                )
                finished = replace(
                    job,
                    status=VideoJobStatus.COMPLETED,
                    video_url=status_result.video_url,
                    created_post_ids=[p.id for p in posts],
                )
                updated.append(self.video_job_repo.update(finished))
            elif status_result.status == VideoJobStatus.FAILED:
                failed = replace(
                    job,
                    status=VideoJobStatus.FAILED,
                    error_message=status_result.error_message,
                )
                updated.append(self.video_job_repo.update(failed))

        return updated

    def list_jobs(self) -> list[VideoGenerationJob]:
        return sorted(self.video_job_repo.list_all(), key=lambda j: j.created_at)

    def get_job(self, job_id: UUID) -> VideoGenerationJob:
        job = self.video_job_repo.get(job_id)
        if job is None:
            raise ValueError("Video generation job not found")
        return job
