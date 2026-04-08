from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Optional
from uuid import UUID

from .models import Account, Post, PostStatus, Provider


class SQLiteAccountRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    external_account_id TEXT NOT NULL,
                    access_token TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add(self, account: Account) -> Account:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO accounts (id, name, provider, external_account_id, access_token, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(account.id),
                    account.name,
                    account.provider.value,
                    account.external_account_id,
                    account.access_token,
                    account.created_at.isoformat(),
                ),
            )
        return account

    def get(self, account_id: UUID) -> Optional[Account]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, provider, external_account_id, access_token, created_at FROM accounts WHERE id=?",
                (str(account_id),),
            ).fetchone()
        if row is None:
            return None
        return Account(
            id=UUID(row[0]),
            name=row[1],
            provider=Provider(row[2]),
            external_account_id=row[3],
            access_token=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )


class SQLitePostRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    published_at TEXT,
                    provider_post_id TEXT,
                    error_message TEXT,
                    retry_count INTEGER NOT NULL,
                    labels TEXT NOT NULL DEFAULT '[]',
                    media_urls TEXT NOT NULL DEFAULT '[]',
                    first_comment TEXT,
                    review_comment TEXT
                )
                """
            )
            self._ensure_columns(conn)

    def _ensure_columns(self, conn) -> None:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(posts)").fetchall()
        }
        if "labels" not in existing:
            conn.execute("ALTER TABLE posts ADD COLUMN labels TEXT NOT NULL DEFAULT '[]'")
        if "media_urls" not in existing:
            conn.execute("ALTER TABLE posts ADD COLUMN media_urls TEXT NOT NULL DEFAULT '[]'")
        if "first_comment" not in existing:
            conn.execute("ALTER TABLE posts ADD COLUMN first_comment TEXT")
        if "review_comment" not in existing:
            conn.execute("ALTER TABLE posts ADD COLUMN review_comment TEXT")

    def add(self, post: Post) -> Post:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO posts (
                    id, account_id, content, scheduled_at, status, published_at,
                    provider_post_id, error_message, retry_count, labels, media_urls,
                    first_comment, review_comment
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(post.id),
                    str(post.account_id),
                    post.content,
                    post.scheduled_at.isoformat(),
                    post.status.value,
                    post.published_at.isoformat() if post.published_at else None,
                    post.provider_post_id,
                    post.error_message,
                    post.retry_count,
                    json.dumps(post.labels),
                    json.dumps(post.media_urls),
                    post.first_comment,
                    post.review_comment,
                ),
            )
        return post

    def update(self, post: Post) -> Post:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE posts
                SET account_id=?, content=?, scheduled_at=?, status=?, published_at=?, provider_post_id=?, error_message=?, retry_count=?, labels=?, media_urls=?, first_comment=?, review_comment=?
                WHERE id=?
                """,
                (
                    str(post.account_id),
                    post.content,
                    post.scheduled_at.isoformat(),
                    post.status.value,
                    post.published_at.isoformat() if post.published_at else None,
                    post.provider_post_id,
                    post.error_message,
                    post.retry_count,
                    json.dumps(post.labels),
                    json.dumps(post.media_urls),
                    post.first_comment,
                    post.review_comment,
                    str(post.id),
                ),
            )
        return post

    def get(self, post_id: UUID) -> Optional[Post]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, account_id, content, scheduled_at, status, published_at, provider_post_id, error_message, retry_count, labels, media_urls, first_comment, review_comment
                FROM posts WHERE id=?
                """,
                (str(post_id),),
            ).fetchone()
        return self._to_post(row)

    def list_all(self) -> list[Post]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, account_id, content, scheduled_at, status, published_at, provider_post_id, error_message, retry_count, labels, media_urls, first_comment, review_comment
                FROM posts
                ORDER BY scheduled_at ASC
                """
            ).fetchall()
        return [self._to_post(row) for row in rows if row is not None]

    def list_due(self, now: datetime) -> list[Post]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, account_id, content, scheduled_at, status, published_at, provider_post_id, error_message, retry_count, labels, media_urls, first_comment, review_comment
                FROM posts
                WHERE status = ? AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
                """,
                (PostStatus.SCHEDULED.value, now.isoformat()),
            ).fetchall()
        return [self._to_post(row) for row in rows if row is not None]

    def _to_post(self, row) -> Optional[Post]:
        if row is None:
            return None
        return Post(
            id=UUID(row[0]),
            account_id=UUID(row[1]),
            content=row[2],
            scheduled_at=datetime.fromisoformat(row[3]),
            status=PostStatus(row[4]),
            published_at=datetime.fromisoformat(row[5]) if row[5] else None,
            provider_post_id=row[6],
            error_message=row[7],
            retry_count=row[8],
            labels=self._decode_json_list(row[9]),
            media_urls=self._decode_json_list(row[10]),
            first_comment=row[11],
            review_comment=row[12],
        )

    def _decode_json_list(self, raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(decoded, list):
            return []
        return [str(item) for item in decoded]
