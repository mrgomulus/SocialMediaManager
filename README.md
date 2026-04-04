# SocialMediaManager

Ein modularer, self-hosted Social-Media-Manager (MVP++), inspiriert von Open-Source-Tools wie Postiz, Mixpost, Socioboard und OpenSMM.

## Enthaltene Funktionen
- Multi-Account-Verwaltung ueber mehrere Provider
- Post-Workflow mit Review: `draft -> in_review -> approved|rejected -> scheduled -> published|failed`
- Scheduler mit Queue-Verarbeitung
- Publish-Pipeline mit Retry-Logik plus exponentiellem Backoff
- Erweiterte Analytics (Status, Erfolgsquote, Retry-Metriken, Provider-Breakdown, 24h-Vorschau)
- Template Engine mit Variablen (`{{variable}}`)
- Hashtag-Gruppen mit Normalisierung und Duplikatkontrolle
- Posting-Zeitslots pro Account plus Quick-Schedule (naechster freier Slot)
- Campaign/Cross-Posting fuer mehrere Accounts
- Post-Metadaten: Labels, Media-URLs, First Comment, Review Comment
- In-Memory Repository-Layer plus SQLite-Repositories (inkl. Metadaten-Persistenz)
- REST API (FastAPI) fuer Kern- und Advanced-Operationen
- Einfacher API-Key Schutz (`X-API-Key`)
- Unit-Tests fuer Kernlogik, Workflow und Persistenz

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

## API-Endpunkte
- `GET /health`
- `POST /accounts`
- `POST /posts`
- `GET /posts`
- `POST /posts/{post_id}/submit`
- `POST /posts/{post_id}/approve`
- `POST /posts/{post_id}/reject`
- `POST /posts/{post_id}/schedule`
- `POST /posts/{post_id}/duplicate`
- `POST /templates`
- `GET /templates`
- `POST /hashtags/groups`
- `GET /hashtags/groups`
- `POST /accounts/{account_id}/timeslots`
- `GET /accounts/{account_id}/timeslots`
- `POST /posts/from-template`
- `POST /posts/quick-schedule`
- `POST /campaigns`
- `POST /publish/run`
- `GET /analytics/summary`

> Hinweis: Bis auf `/health` erwarten Endpunkte den Header `X-API-Key`.

## Projektstruktur
- `src/social_media_manager/models.py`: Domaenenmodelle
- `src/social_media_manager/repositories.py`: In-Memory Repositories
- `src/social_media_manager/sqlite_repositories.py`: SQLite Persistenz
- `src/social_media_manager/providers.py`: Provider-Abstraktion plus Demo-Provider
- `src/social_media_manager/services.py`: Business- und Advanced-Services
- `src/social_media_manager/scheduler.py`: Scheduler/Worker Logik
- `src/social_media_manager/api.py`: REST API Layer
- `src/social_media_manager/demo.py`: Demo-Ablauf mit erweiterten Features
- `docs/GIANT_EXECUTION_PROMPT.md`: Living Prompt inklusive Fortschrittsprotokoll

## Naechste Schritte
- OAuth-Flow je Plattform
- Webhook-Inbox plus Kommentar-Moderation
- RBAC plus Freigabe-Matrix pro Team
- Analytics mit UTM und Zeitreihen
