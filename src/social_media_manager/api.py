from __future__ import annotations

import os
from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .models import Provider
from .providers import ProviderRegistry
from .repositories import InMemoryAccountRepository, InMemoryPostRepository
from .services import AccountService, AnalyticsService, PostService, PublishingService

API_KEY = os.getenv("SMM_API_KEY", "dev-key")

app = FastAPI(title="SocialMediaManager API", version="0.3.0")

account_repo = InMemoryAccountRepository()
post_repo = InMemoryPostRepository()
provider_registry = ProviderRegistry()
account_service = AccountService(account_repo)
post_service = PostService(post_repo)
publishing_service = PublishingService(account_repo, post_repo, provider_registry)
analytics_service = AnalyticsService(post_repo)


class AccountCreate(BaseModel):
    name: str
    provider: Provider
    external_account_id: str
    access_token: str


class PostCreate(BaseModel):
    account_id: UUID
    content: str = Field(min_length=1, max_length=280)
    scheduled_at: datetime


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


@app.post("/posts")
def create_post(payload: PostCreate, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        post = post_service.create_draft_post(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(post.id), "status": post.status.value}


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


@app.post("/posts/{post_id}/schedule")
def schedule(post_id: UUID, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    try:
        post = post_service.schedule(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(post.id), "status": post.status.value}


@app.post("/publish/run")
def run_publish(x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    processed = publishing_service.publish_due_posts(datetime.utcnow())
    return {"processed": len(processed)}


@app.get("/analytics/summary")
def analytics_summary(x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    return analytics_service.summary()
