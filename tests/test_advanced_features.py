from datetime import datetime, timedelta

import pytest

from social_media_manager.models import PostStatus, Provider
from social_media_manager.repositories import (
    InMemoryAccountRepository,
    InMemoryHashtagGroupRepository,
    InMemoryPostRepository,
    InMemoryPostingSlotRepository,
    InMemoryTemplateRepository,
)
from social_media_manager.services import (
    AccountService,
    AnalyticsService,
    CampaignService,
    HashtagGroupService,
    PostService,
    QueuePlannerService,
    TemplateService,
)


def test_template_hashtags_and_slot_planning_flow():
    accounts = InMemoryAccountRepository()
    posts = InMemoryPostRepository()
    templates = InMemoryTemplateRepository()
    hashtags = InMemoryHashtagGroupRepository()
    slots = InMemoryPostingSlotRepository()

    account = AccountService(accounts).connect_account(
        name="Brand A",
        provider=Provider.GENERIC,
        external_account_id="acc-1",
        access_token="token",
    )
    post_service = PostService(posts)
    template_service = TemplateService(templates)
    hashtag_service = HashtagGroupService(hashtags)
    queue_service = QueuePlannerService(slots)

    template = template_service.create_template(
        name="Launch Template",
        body="Neue Version von {{product}} ist live. -- {{brand}}",
        default_variables={"brand": "ACME"},
    )
    group = hashtag_service.create_group(
        name="Launch Tags",
        hashtags=["launch", "#ACME", "launch"],
    )
    queue_service.replace_slots(
        account.id,
        [
            {"weekday": 0, "hour": 9, "minute": 30},
            {"weekday": 2, "hour": 14, "minute": 0},
        ],
    )

    monday_morning = datetime(2026, 1, 5, 8, 0, 0)
    next_slot = queue_service.next_available_slot(account.id, from_time=monday_morning)
    assert next_slot == datetime(2026, 1, 5, 9, 30, 0)

    content = template_service.render(template.id, {"product": "SocialManager"})
    suffix = hashtag_service.compose_hashtag_suffix([group.id])
    scheduled_post = post_service.create_scheduled_post(
        account_id=account.id,
        content=f"{content}\n\n{suffix}",
        scheduled_at=next_slot,
        labels=["launch", "product"],
        media_urls=["https://cdn.example.com/launch.png"],
        first_comment="Feedback willkommen!",
    )

    assert scheduled_post.status == PostStatus.SCHEDULED
    assert "#launch" in scheduled_post.content.lower()
    assert scheduled_post.labels == ["launch", "product"]
    assert scheduled_post.media_urls == ["https://cdn.example.com/launch.png"]
    assert scheduled_post.first_comment == "Feedback willkommen!"


def test_post_reject_and_resubmit_workflow():
    post_repo = InMemoryPostRepository()
    service = PostService(post_repo)
    post = service.create_draft_post(
        account_id="acc",
        content="Review me",
        scheduled_at=datetime.utcnow() + timedelta(minutes=30),
    )
    service.submit_for_review(post.id)

    rejected = service.reject(post.id, "Bitte CTA klarer formulieren")
    assert rejected.status == PostStatus.REJECTED
    assert rejected.review_comment == "Bitte CTA klarer formulieren"

    resubmitted = service.submit_for_review(post.id)
    assert resubmitted.status == PostStatus.IN_REVIEW


def test_campaign_service_creates_posts_for_multiple_accounts():
    account_repo = InMemoryAccountRepository()
    post_repo = InMemoryPostRepository()
    account_service = AccountService(account_repo)
    post_service = PostService(post_repo)
    campaign_service = CampaignService(post_service)

    a1 = account_service.connect_account(
        name="A1",
        provider=Provider.GENERIC,
        external_account_id="a1",
        access_token="t1",
    )
    a2 = account_service.connect_account(
        name="A2",
        provider=Provider.POSTIZ_INSPIRED,
        external_account_id="a2",
        access_token="t2",
    )

    posts = campaign_service.create_campaign_posts(
        account_ids=[a1.id, a2.id, a1.id],
        content="Campaign Post",
        scheduled_at=datetime.utcnow() + timedelta(hours=2),
        labels=["campaign"],
    )

    assert len(posts) == 2
    assert all(post.status == PostStatus.SCHEDULED for post in posts)
    assert all(post.labels == ["campaign"] for post in posts)


def test_analytics_extended_metrics():
    account_repo = InMemoryAccountRepository()
    post_repo = InMemoryPostRepository()
    account_service = AccountService(account_repo)
    post_service = PostService(post_repo)

    generic = account_service.connect_account(
        name="Generic",
        provider=Provider.GENERIC,
        external_account_id="g",
        access_token="t",
    )
    postiz = account_service.connect_account(
        name="Postiz",
        provider=Provider.POSTIZ_INSPIRED,
        external_account_id="p",
        access_token="t",
    )

    soon = datetime.utcnow() + timedelta(hours=1)
    late = datetime.utcnow() + timedelta(days=2)
    published_time = datetime.utcnow() + timedelta(minutes=30)

    p1 = post_service.create_scheduled_post(generic.id, "Upcoming", soon)
    p2 = post_service.create_scheduled_post(postiz.id, "Later", late)
    p3 = post_service.create_scheduled_post(postiz.id, "Done", published_time)
    p3.status = PostStatus.PUBLISHED
    post_repo.update(p3)

    summary = AnalyticsService(post_repo, account_repo=account_repo).summary()
    assert summary["total_posts"] == 3
    assert summary["upcoming_posts_24h"] >= 1
    assert summary["by_provider"]["generic"] == 1
    assert summary["by_provider"]["postiz_inspired"] == 2
    assert summary["publish_success_rate"] == pytest.approx(1 / 3, rel=1e-2)
    assert summary["failed_posts"] == 0
    assert summary["average_retry_count"] == 0.0

    # Keep references in scope to avoid lint false positives in some environments.
    assert p1.id is not None
    assert p2.id is not None


def test_queue_slots_validate_input():
    queue_service = QueuePlannerService(InMemoryPostingSlotRepository())
    with pytest.raises(ValueError):
        queue_service.replace_slots("acc", [{"weekday": 7, "hour": 10, "minute": 0}])
