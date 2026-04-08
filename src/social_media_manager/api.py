from __future__ import annotations

import os
from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .models import PostStatus, Provider, VideoGenerationStatus
from .providers import ProviderRegistry, VideoGenerationProviderRegistry
from .repositories import (
    InMemoryAccountRepository,
    InMemoryHashtagGroupRepository,
    InMemoryPostRepository,
    InMemoryPostingSlotRepository,
    InMemoryTemplateRepository,
    InMemoryVideoJobRepository,
)
from .services import (
    AccountService,
    AnalyticsService,
    CampaignService,
    HashtagGroupService,
    PostService,
    PublishingService,
    QueuePlannerService,
    TemplateService,
    VideoGenerationService,
)

API_KEY = os.getenv("SMM_API_KEY", "dev-key")

app = FastAPI(title="SocialMediaManager API", version="0.5.0")

account_repo = InMemoryAccountRepository()
post_repo = InMemoryPostRepository()
template_repo = InMemoryTemplateRepository()
hashtag_group_repo = InMemoryHashtagGroupRepository()
posting_slot_repo = InMemoryPostingSlotRepository()
video_job_repo = InMemoryVideoJobRepository()
provider_registry = ProviderRegistry()
video_provider_registry = VideoGenerationProviderRegistry()
account_service = AccountService(account_repo)
post_service = PostService(post_repo)
template_service = TemplateService(template_repo)
hashtag_group_service = HashtagGroupService(hashtag_group_repo)
queue_planner_service = QueuePlannerService(posting_slot_repo)
campaign_service = CampaignService(post_service)
publishing_service = PublishingService(account_repo, post_repo, provider_registry)
analytics_service = AnalyticsService(post_repo, account_repo=account_repo)
video_generation_service = VideoGenerationService(
    job_repo=video_job_repo,
    post_service=post_service,
    video_provider_registry=video_provider_registry,
)


class AccountCreate(BaseModel):
    name: str
    provider: Provider
    external_account_id: str
    access_token: str


class PostCreate(BaseModel):
    account_id: UUID
    content: str = Field(min_length=1, max_length=280)
    scheduled_at: datetime
    labels: list[str] = Field(default_factory=list)
    media_urls: list[str] = Field(default_factory=list)
    first_comment: str | None = None


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=1000)
    default_variables: dict[str, str] = Field(default_factory=dict)


class HashtagGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    hashtags: list[str] = Field(default_factory=list)


class TimeSlotIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)


class TimeSlotBulkUpsert(BaseModel):
    slots: list[TimeSlotIn] = Field(default_factory=list)


class PostFromTemplateCreate(BaseModel):
    account_id: UUID
    template_id: UUID
    variables: dict[str, str] = Field(default_factory=dict)
    scheduled_at: datetime | None = None
    hashtag_group_ids: list[UUID] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    media_urls: list[str] = Field(default_factory=list)
    first_comment: str | None = None


class QuickScheduleCreate(BaseModel):
    account_id: UUID
    content: str = Field(min_length=1, max_length=280)
    hashtag_group_ids: list[UUID] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    media_urls: list[str] = Field(default_factory=list)
    first_comment: str | None = None


class CampaignCreate(BaseModel):
    account_ids: list[UUID] = Field(default_factory=list)
    content: str = Field(min_length=1, max_length=280)
    scheduled_at: datetime
    labels: list[str] = Field(default_factory=list)
    media_urls: list[str] = Field(default_factory=list)
    first_comment: str | None = None


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class VideoJobCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    account_ids: list[UUID] = Field(default_factory=list)
    post_content: str = Field(min_length=1, max_length=280)
    scheduled_publish_at: datetime | None = None
    labels: list[str] = Field(default_factory=list)


def _append_hashtags(content: str, hashtag_suffix: str) -> str:
    if not hashtag_suffix:
        return content
    return f"{content}\n\n{hashtag_suffix}"


def _serialize_post(post) -> dict:
    return {
        "id": str(post.id),
        "account_id": str(post.account_id),
        "content": post.content,
        "status": post.status.value,
        "scheduled_at": post.scheduled_at.isoformat(),
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "provider_post_id": post.provider_post_id,
        "error_message": post.error_message,
        "retry_count": post.retry_count,
        "labels": post.labels,
        "media_urls": post.media_urls,
        "first_comment": post.first_comment,
        "review_comment": post.review_comment,
    }


def _serialize_video_job(job) -> dict:
    return {
        "id": str(job.id),
        "prompt": job.prompt,
        "account_ids": [str(aid) for aid in job.account_ids],
        "post_content": job.post_content,
        "status": job.status.value,
        "video_url": job.video_url,
        "provider_job_id": job.provider_job_id,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "scheduled_publish_at": job.scheduled_publish_at.isoformat() if job.scheduled_publish_at else None,
        "labels": job.labels,
        "published_post_ids": [str(pid) for pid in job.published_post_ids],
    }


def _auth(x_api_key: str | None) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@app.post("/accounts")
def create_account(payload: AccountCreate, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    account = account_service.connect_account(**payload.model_dump())
    return {"id": str(account.id), "provider": account.provider.value, "name": account.name}


@app.get("/accounts")
def list_accounts(x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    accounts = account_repo.list_all()
    return {
        "items": [
            {
                "id": str(a.id),
                "name": a.name,
                "provider": a.provider.value,
                "external_account_id": a.external_account_id,
                "created_at": a.created_at.isoformat(),
            }
            for a in accounts
        ],
        "count": len(accounts),
    }


@app.post("/posts")
def create_post(payload: PostCreate, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        post = post_service.create_draft_post(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(post.id), "status": post.status.value}


@app.get("/posts")
def list_posts(
    account_id: UUID | None = None,
    status: PostStatus | None = None,
    x_api_key: str | None = Header(default=None),
):
    _auth(x_api_key)
    posts = post_service.list_posts(account_id=account_id, status=status)
    return {"items": [_serialize_post(post) for post in posts], "count": len(posts)}


@app.post("/posts/{post_id}/submit")
def submit(post_id: UUID, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        post = post_service.submit_for_review(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(post.id), "status": post.status.value}


@app.post("/posts/{post_id}/approve")
def approve(post_id: UUID, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        post = post_service.approve(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(post.id), "status": post.status.value}


@app.post("/posts/{post_id}/reject")
def reject(post_id: UUID, payload: RejectRequest, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        post = post_service.reject(post_id, payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(post.id), "status": post.status.value, "review_comment": post.review_comment}


@app.post("/posts/{post_id}/schedule")
def schedule(post_id: UUID, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        post = post_service.schedule(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(post.id), "status": post.status.value}


@app.post("/posts/{post_id}/duplicate")
def duplicate(post_id: UUID, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        post = post_service.duplicate_as_draft(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(post.id), "status": post.status.value}


@app.post("/templates")
def create_template(payload: TemplateCreate, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        template = template_service.create_template(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(template.id), "name": template.name}


@app.get("/templates")
def list_templates(x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    templates = template_service.list_templates()
    return {
        "items": [
            {
                "id": str(template.id),
                "name": template.name,
                "body": template.body,
                "default_variables": template.default_variables,
            }
            for template in templates
        ],
        "count": len(templates),
    }


@app.post("/hashtags/groups")
def create_hashtag_group(payload: HashtagGroupCreate, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        group = hashtag_group_service.create_group(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(group.id), "name": group.name, "hashtags": group.hashtags}


@app.get("/hashtags/groups")
def list_hashtag_groups(x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    groups = hashtag_group_service.list_groups()
    return {
        "items": [{"id": str(group.id), "name": group.name, "hashtags": group.hashtags} for group in groups],
        "count": len(groups),
    }


@app.post("/accounts/{account_id}/timeslots")
def replace_time_slots(account_id: UUID, payload: TimeSlotBulkUpsert, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        slots = queue_planner_service.replace_slots(
            account_id=account_id,
            slots=[slot.model_dump() for slot in payload.slots],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "account_id": str(account_id),
        "slots": [{"weekday": slot.weekday, "hour": slot.hour, "minute": slot.minute} for slot in slots],
    }


@app.get("/accounts/{account_id}/timeslots")
def list_time_slots(account_id: UUID, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    slots = queue_planner_service.list_slots(account_id)
    return {
        "account_id": str(account_id),
        "slots": [{"weekday": slot.weekday, "hour": slot.hour, "minute": slot.minute} for slot in slots],
    }


@app.post("/posts/from-template")
def create_post_from_template(payload: PostFromTemplateCreate, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        content = template_service.render(payload.template_id, payload.variables)
        hashtag_suffix = hashtag_group_service.compose_hashtag_suffix(payload.hashtag_group_ids)
        scheduled_at = payload.scheduled_at or queue_planner_service.next_available_slot(payload.account_id)
        post = post_service.create_scheduled_post(
            account_id=payload.account_id,
            content=_append_hashtags(content, hashtag_suffix),
            scheduled_at=scheduled_at,
            labels=payload.labels,
            media_urls=payload.media_urls,
            first_comment=payload.first_comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_post(post)


@app.post("/posts/quick-schedule")
def quick_schedule(payload: QuickScheduleCreate, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        scheduled_at = queue_planner_service.next_available_slot(payload.account_id)
        hashtag_suffix = hashtag_group_service.compose_hashtag_suffix(payload.hashtag_group_ids)
        post = post_service.create_scheduled_post(
            account_id=payload.account_id,
            content=_append_hashtags(payload.content, hashtag_suffix),
            scheduled_at=scheduled_at,
            labels=payload.labels,
            media_urls=payload.media_urls,
            first_comment=payload.first_comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_post(post)


@app.post("/campaigns")
def create_campaign(payload: CampaignCreate, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        posts = campaign_service.create_campaign_posts(
            account_ids=payload.account_ids,
            content=payload.content,
            scheduled_at=payload.scheduled_at,
            labels=payload.labels,
            media_urls=payload.media_urls,
            first_comment=payload.first_comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(posts), "items": [_serialize_post(post) for post in posts]}


@app.post("/publish/run")
def run_publish(x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    processed = publishing_service.publish_due_posts(datetime.utcnow())
    return {"processed": len(processed)}


@app.get("/analytics/summary")
def analytics_summary(x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    return analytics_service.summary()


# ---------------------------------------------------------------------------
# AI Video Generation endpoints
# ---------------------------------------------------------------------------


@app.post("/video-jobs")
def create_video_job(payload: VideoJobCreate, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        job = video_generation_service.create_job(
            prompt=payload.prompt,
            account_ids=payload.account_ids,
            post_content=payload.post_content,
            scheduled_publish_at=payload.scheduled_publish_at,
            labels=payload.labels,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_video_job(job)


@app.get("/video-jobs")
def list_video_jobs(
    status: VideoGenerationStatus | None = None,
    x_api_key: str | None = Header(default=None),
):
    _auth(x_api_key)
    jobs = video_generation_service.list_jobs(status=status)
    return {"items": [_serialize_video_job(j) for j in jobs], "count": len(jobs)}


@app.get("/video-jobs/{job_id}")
def get_video_job(job_id: UUID, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    job = video_generation_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Video job not found")
    return _serialize_video_job(job)


@app.post("/video-jobs/process")
def process_video_jobs(x_api_key: str | None = Header(default=None)):
    """Submit all PENDING jobs to the AI provider and poll PROCESSING jobs."""
    _auth(x_api_key)
    now = datetime.utcnow()
    submitted = video_generation_service.process_pending_jobs(now)
    polled = video_generation_service.poll_processing_jobs(now)
    return {"submitted": len(submitted), "polled": len(polled)}


@app.post("/video-jobs/auto-upload")
def auto_upload_videos(x_api_key: str | None = Header(default=None)):
    """Publish all COMPLETED video jobs to their target social media accounts."""
    _auth(x_api_key)
    posts = video_generation_service.auto_publish_completed_jobs(datetime.utcnow())
    return {"published_posts": len(posts), "items": [_serialize_post(p) for p in posts]}
