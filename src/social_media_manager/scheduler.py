from __future__ import annotations

from datetime import datetime, timedelta

from .services import PublishingService


class SchedulerWorker:
    """Einfacher Worker, der in festen Intervallen due posts veröffentlicht."""

    def __init__(self, publishing_service: PublishingService, tick_seconds: int = 30) -> None:
        if tick_seconds <= 0:
            raise ValueError("tick_seconds must be > 0")
        self.publishing_service = publishing_service
        self.tick_seconds = tick_seconds

    def run_once(self, now: datetime | None = None):
        now = now or datetime.utcnow()
        return self.publishing_service.publish_due_posts(now)

    def simulate(self, start: datetime, ticks: int) -> list[dict]:
        if ticks < 0:
            raise ValueError("ticks must be >= 0")
        events: list[dict] = []
        current = start
        for _ in range(ticks):
            changed = self.run_once(current)
            events.append({"time": current.isoformat(), "processed": len(changed)})
            current += timedelta(seconds=self.tick_seconds)
        return events
