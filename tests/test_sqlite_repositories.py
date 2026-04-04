from datetime import datetime, timedelta

from social_media_manager.models import Account, Post, PostStatus, Provider
from social_media_manager.sqlite_repositories import SQLiteAccountRepository, SQLitePostRepository


def test_sqlite_account_and_post_roundtrip(tmp_path):
    db_path = str(tmp_path / "smm.db")
    account_repo = SQLiteAccountRepository(db_path)
    post_repo = SQLitePostRepository(db_path)

    account = Account(
        name="SQLite Brand",
        provider=Provider.GENERIC,
        external_account_id="ext-1",
        access_token="token",
    )
    account_repo.add(account)

    loaded_account = account_repo.get(account.id)
    assert loaded_account is not None
    assert loaded_account.name == "SQLite Brand"

    post = Post(
        account_id=account.id,
        content="Persist me",
        scheduled_at=datetime.utcnow() + timedelta(minutes=5),
        status=PostStatus.SCHEDULED,
    )
    post_repo.add(post)

    loaded_post = post_repo.get(post.id)
    assert loaded_post is not None
    assert loaded_post.status == PostStatus.SCHEDULED

    post.status = PostStatus.FAILED
    post.scheduled_at = datetime.utcnow() + timedelta(minutes=15)
    post.retry_count = 2
    post_repo.update(post)

    updated = post_repo.get(post.id)
    assert updated is not None
    assert updated.status == PostStatus.FAILED
    assert updated.retry_count == 2

    due = post_repo.list_due(datetime.utcnow() + timedelta(hours=1))
    assert len(due) == 0
