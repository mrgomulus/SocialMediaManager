from datetime import datetime, timedelta

from .models import Provider
from .providers import ProviderRegistry
from .repositories import (
    InMemoryAccountRepository,
    InMemoryHashtagGroupRepository,
    InMemoryPostRepository,
    InMemoryPostingSlotRepository,
    InMemoryTemplateRepository,
)
from .scheduler import SchedulerWorker
from .services import (
    AccountService,
    AnalyticsService,
    HashtagGroupService,
    PostService,
    PublishingService,
    QueuePlannerService,
    TemplateService,
)


def main() -> None:
    account_repo = InMemoryAccountRepository()
    post_repo = InMemoryPostRepository()
    template_repo = InMemoryTemplateRepository()
    hashtag_repo = InMemoryHashtagGroupRepository()
    slot_repo = InMemoryPostingSlotRepository()
    providers = ProviderRegistry()

    account_service = AccountService(account_repo)
    post_service = PostService(post_repo)
    template_service = TemplateService(template_repo)
    hashtag_service = HashtagGroupService(hashtag_repo)
    queue_service = QueuePlannerService(slot_repo)
    publishing_service = PublishingService(account_repo, post_repo, providers)
    analytics_service = AnalyticsService(post_repo, account_repo=account_repo)
    worker = SchedulerWorker(publishing_service, tick_seconds=10)

    account = account_service.connect_account(
        name="Brand DE",
        provider=Provider.POSTIZ_INSPIRED,
        external_account_id="acc-123",
        access_token="secret",
    )

    template = template_service.create_template(
        name="Launch Template",
        body="Hallo {{audience}}! Unser neuer Beitrag zu {{topic}} ist online.",
        default_variables={"audience": "Community"},
    )
    hashtag_group = hashtag_service.create_group(name="Launch", hashtags=["Launch", "SocialMedia"])
    slot_reference = datetime.utcnow() + timedelta(minutes=1)
    queue_service.replace_slots(
        account.id,
        [{"weekday": slot_reference.weekday(), "hour": slot_reference.hour, "minute": slot_reference.minute}],
    )

    next_slot = queue_service.next_available_slot(account.id)
    content = template_service.render(template.id, {"topic": "unser Produktupdate"})
    full_content = f"{content}\n\n{hashtag_service.compose_hashtag_suffix([hashtag_group.id])}"

    draft = post_service.create_draft_post(
        account.id,
        full_content,
        scheduled_at=next_slot,
        labels=["launch", "community"],
    )
    reviewed = post_service.submit_for_review(draft.id)
    post_service.reject(reviewed.id, "Bitte noch Call-to-Action ergaenzen")
    post_service.update_draft_content(draft.id, f"{full_content}\nJetzt testen und Feedback geben.")
    post_service.submit_for_review(draft.id)
    post_service.approve(draft.id)
    post_service.schedule(draft.id)

    timeline = worker.simulate(start=datetime.utcnow(), ticks=3)
    for event in timeline:
        print(event)

    print("Analytics:", analytics_service.summary())


if __name__ == "__main__":
    main()
