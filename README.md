# SocialMediaManager

Ein modularer, self-hosted Social-Media-Manager (MVP++), inspiriert von Open-Source-Tools wie Postiz, Mixpost, Socioboard und OpenSMM.

## Enthaltene Funktionen
- Multi-Account-Verwaltung ueber mehrere Provider: YouTube, TikTok, Instagram, Twitter, Facebook, LinkedIn und generische Plattformen
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
- **KI-Video-Generierung**: Integration externer KI-Video-Dienste (z.B. RunwayML, Pika) ueber HTTP-API
- **Automatischer Video-Upload**: Generierte Videos werden automatisch als Posts auf allen konfigurierten Social-Media-Kanaelen eingeplant und hochgeladen
- Unit-Tests fuer Kernlogik, Workflow, Persistenz und KI-Video-Integration

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

## KI-Video-Workflow

1. **Externe KI-Video-Dienst registrieren** (einmalig):
   ```bash
   curl -X POST http://localhost:8000/video-providers/register \
     -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
     -d '{"provider": "runway", "api_url": "https://api.runwayml.com/v1", "api_key": "your-api-key"}'
   ```

2. **KI-Video-Job erstellen** (Video generieren und auf Kanaelen hochladen):
   ```bash
   curl -X POST http://localhost:8000/video-jobs \
     -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
     -d '{
       "prompt": "A futuristic city at sunset, cinematic quality",
       "account_ids": ["<youtube-account-id>", "<tiktok-account-id>"],
       "post_caption": "Check out this AI-generated city! #AI #FutureCities",
       "video_provider": "runway",
       "scheduled_at": "2026-05-01T12:00:00"
     }'
   ```

3. **Status abfragen**:
   ```bash
   curl http://localhost:8000/video-jobs/<job-id> -H "X-API-Key: dev-key"
   ```

4. **Verarbeitung ausloesen** (pollt externe API und erstellt Posts bei fertigen Videos):
   ```bash
   curl -X POST http://localhost:8000/video-jobs/poll -H "X-API-Key: dev-key"
   ```

## API-Endpunkte
- `GET /health`
- `GET /accounts`
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
- `POST /video-providers/register` *(KI-Video-Dienst registrieren)*
- `POST /video-jobs` *(KI-Video-Job erstellen)*
- `GET /video-jobs` *(Alle Video-Jobs auflisten)*
- `GET /video-jobs/{job_id}` *(Video-Job-Status abrufen)*
- `POST /video-jobs/poll` *(Verarbeitung abgeschlossener Video-Jobs ausloesen)*

> Hinweis: Bis auf `/health` erwarten Endpunkte den Header `X-API-Key`.

## Unterstuetzte Plattformen

| Provider | Enum-Wert |
|---|---|
| YouTube | `youtube` |
| TikTok | `tiktok` |
| Instagram | `instagram` |
| Twitter / X | `twitter` |
| Facebook | `facebook` |
| LinkedIn | `linkedin` |
| Postiz-kompatibel | `postiz_inspired` |
| Mixpost-kompatibel | `mixpost_inspired` |
| Generisch | `generic` |

## Unterstuetzte KI-Video-Anbieter

| Anbieter | Enum-Wert |
|---|---|
| RunwayML | `runway` |
| Pika Labs | `pika` |
| Generisch (Demo) | `generic` |

Eigene Dienste koennen ueber `POST /video-providers/register` mit URL und API-Key hinzugefuegt werden.

## Projektstruktur
- `src/social_media_manager/models.py`: Domaenenmodelle (inkl. VideoGenerationJob, VideoProvider)
- `src/social_media_manager/repositories.py`: In-Memory Repositories (inkl. InMemoryVideoGenerationJobRepository)
- `src/social_media_manager/sqlite_repositories.py`: SQLite Persistenz
- `src/social_media_manager/providers.py`: Provider-Abstraktion plus Demo-Provider und AI-Video-Clients
- `src/social_media_manager/services.py`: Business- und Advanced-Services (inkl. VideoGenerationService)
- `src/social_media_manager/scheduler.py`: Scheduler/Worker Logik
- `src/social_media_manager/api.py`: REST API Layer
- `src/social_media_manager/demo.py`: Demo-Ablauf mit erweiterten Features
- `docs/GIANT_EXECUTION_PROMPT.md`: Living Prompt inklusive Fortschrittsprotokoll

## Naechste Schritte
- OAuth-Flow je Plattform
- Webhook-Inbox plus Kommentar-Moderation
- RBAC plus Freigabe-Matrix pro Team
- Analytics mit UTM und Zeitreihen
- Plattformspezifische Post-Validierung (Zeichenlaenge, Formate)
- Asynchrone Video-Job-Verarbeitung (Background Worker)
