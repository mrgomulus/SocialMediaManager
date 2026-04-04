from datetime import datetime, timedelta

from .models import Provider
from .providers import ProviderRegistry
from .repositories import InMemoryAccountRepository, InMemoryPostRepository
from .scheduler import SchedulerWorker
from .services import AccountService, AnalyticsService, PostService, PublishingService


def main() -> None:
    account_repo = InMemoryAccountRepository()
    post_repo = InMemoryPostRepository()
    providers = ProviderRegistry()

    account_service = AccountService(account_repo)
    post_service = PostService(post_repo)
    publishing_service = PublishingService(account_repo, post_repo, providers)
    analytics_service = AnalyticsService(post_repo)
    worker = SchedulerWorker(publishing_service, tick_seconds=10)

    account = account_service.connect_account(
        name="Brand DE",
        provider=Provider.POSTIZ_INSPIRED,
        external_account_id="acc-123",
        access_token="secret",
    )

    draft = post_service.create_draft_post(
        account.id,
        "Hallo Welt! Unser neuer Beitrag ist online.",
        scheduled_at=datetime.utcnow() + timedelta(seconds=5),
    )
    post_service.submit_for_review(draft.id)
    post_service.approve(draft.id)
    post_service.schedule(draft.id)

    timeline = worker.simulate(start=datetime.utcnow(), ticks=3)
    for event in timeline:
        print(event)

    print("Analytics:", analytics_service.summary())


if __name__ == "__main__":
    main()
