# SocialMediaManager

Ein modularer Open-Source-orientierter Social-Media-Manager (MVP+), der als Grundlage für die Integration weiterer Funktionen nach Vorbild von Postiz, Mixpost und ähnlichen Projekten dient.

## Enthaltene Funktionen
- Multi-Account-Verwaltung über mehrere Provider
- Post-Workflow: `draft -> in_review -> approved -> scheduled -> published|failed`
- Scheduler mit Queue-Verarbeitung
- Publish-Pipeline mit Retry-Logik + exponentiellem Backoff
- Analytics-Zusammenfassung
- In-Memory Repository-Layer + SQLite-Repositories
- REST API (FastAPI) für Kernoperationen
- Einfacher API-Key Schutz (`X-API-Key`)
- Unit-Tests für Kernlogik, Workflow und Persistenz

## Schnellstart
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python -m src.social_media_manager.demo
export SMM_API_KEY=dev-key
uvicorn src.social_media_manager.api:app --reload
```

## API-Endpunkte (MVP)
- `GET /health`
- `POST /accounts`
- `POST /posts`
- `POST /posts/{post_id}/submit`
- `POST /posts/{post_id}/approve`
- `POST /posts/{post_id}/schedule`
- `POST /publish/run`
- `GET /analytics/summary`

> Hinweis: Bis auf `/health` erwarten Endpunkte den Header `X-API-Key`.

## Projektstruktur
- `src/social_media_manager/models.py`: Domänenmodelle
- `src/social_media_manager/repositories.py`: In-Memory Repositories
- `src/social_media_manager/sqlite_repositories.py`: SQLite Persistenz
- `src/social_media_manager/providers.py`: Provider-Abstraktion + Demo-Provider
- `src/social_media_manager/services.py`: Business-Logik
- `src/social_media_manager/scheduler.py`: Scheduler/Worker Logik
- `src/social_media_manager/api.py`: REST API Layer
- `src/social_media_manager/demo.py`: Demo-Ablauf

## Nächste Schritte
- OAuth-Flow je Plattform
- Webhook-Inbox + Kommentar-Moderation
- Team-Rollen und Freigabe-Matrix
- Analytics mit UTM und Zeitreihen
