# Gigantischer Umsetzungs-Prompt (Living Prompt)

## Zielbild
Baue aus dem bestehenden SocialMediaManager-MVP eine deutlich erweiterte, praxisnahe Open-Source-Social-Media-Management-Plattform mit Fokus auf:
- Multi-Channel Publishing
- Planungs- und Wiederverwendungs-Workflows
- Team- und Freigabe-Qualitaet
- Analytics und operative Effizienz

Dieses Dokument ist ein laufendes Arbeitsdokument. Nach jedem abgeschlossenen Funktionsblock wird der Status direkt hier aktualisiert.

---

## Recherche-Notizen aus Open-Source-Tools (Schritt 1 abgeschlossen)

### 1) Postiz (`gitroomhq/postiz-app`)
Quelle: https://github.com/gitroomhq/postiz-app
Relevante Muster:
- Cross-Platform Scheduling ueber viele Netzwerke
- Team-Kollaboration und Workspaces
- Analytics
- API/Automation (n8n/Make/Zapier)
- AI-gestuetzte Content-Workflows

### 2) Mixpost (`inovector/mixpost`)
Quelle: https://github.com/inovector/mixpost
Relevante Muster:
- Queue plus Calendar Management
- Post-Varianten/Conditions je Netzwerk
- Media Library
- Team/Workspace Konzepte
- Templates, Dynamic Variables, Hashtag Groups

### 3) Socioboard (`socioboard/Socioboard-5.0`)
Quelle: https://github.com/socioboard/Socioboard-5.0
Relevante Muster:
- Multi-Account Management
- Team Collaboration, Permissions, Tasking
- RSS-basierte Content-Curation
- Auto-Reports
- Analytics/Reporting

### 4) Shoutify (`TechSquidTV/Shoutify`, archiviert)
Quelle: https://github.com/TechSquidTV/Shoutify
Relevante Muster:
- Multi-Platform-Postings
- Scheduling inkl. Thread-Use-Cases
- Event-/DM-nahe Planungsansatz-Ideen

### 5) SocialRing (`sanjipun/socialring`)
Quelle: https://github.com/sanjipun/socialring
Relevante Muster:
- Multi-Provider OAuth-Setup-Dokumentation
- Plattformfokus auf operatives Posting in mehrere Netzwerke

### 6) OpenSMM (`vaughngx4/OpenSMM`)
Quelle: https://github.com/vaughngx4/OpenSMM
Relevante Muster:
- Time-Slots plus Quick-Post
- Media Gallery / Attachment-Reuse
- Reschedule alter Posts
- Fokus auf self-hosted, pragmatisches MVP

### 7) Bulkit (`questpie/bulkit.dev`)
Quelle: https://github.com/questpie/bulkit.dev
Relevante Muster:
- Bulk-/Batch-Post-Orchestrierung
- Multi-Account und Performance-Analyse-Fokus

### 8) TryPost (`castellanosllc/trypost.it`)
Quelle: https://github.com/castellanosllc/trypost.it
Relevante Muster:
- Visual Calendar plus Auto-Publishing plus Team-Flows (Produktpositionierung)
- Fokus auf Creator-freundliche UX

---

## Architekturleitplanken fuer diese Codebasis
- Bestehende Kernlogik (`services.py`, `api.py`, `repositories.py`) bleibt Rueckgrat.
- Erweiterungen bauen modular auf bestehenden Services auf.
- Keine Breaking Changes fuer vorhandene Tests und Flows.
- Jede neue Funktion bekommt Tests.
- API bleibt schlank und explizit.

---

## Umsetzungs-Backlog (autonom, in Bloecken)

### Block A - Domain plus Repositories erweitern
- [x] Neue Domain-Objekte: ContentTemplate, HashtagGroup, PostingTimeSlot
- [x] Post-Metadaten erweitert (Labels, Media-Refs, Review-Feedback)
- [x] In-Memory-Repositories fuer Templates, Hashtag-Gruppen, Time-Slots
- [x] SQLite-Persistenz fuer neue Post-Metadaten gehaertet

### Block B - Services deutlich ausbauen
- [x] TemplateService (Variable Rendering, Validierung, Wiederverwendung)
- [x] HashtagGroupService (Normalisierung, Zusammenfuehrung, Duplikatkontrolle)
- [x] QueuePlannerService (Time-Slots plus naechster freier Slot)
- [x] CampaignService (Cross-Posting auf mehrere Accounts)
- [x] PostService Workflow-Upgrade (Reject plus Duplicate plus Filter)
- [x] AnalyticsService erweitert (upcoming_24h, retries, provider breakdown)

### Block C - API ausbauen
- [x] Templates CRUD-light Endpunkte
- [x] Hashtag-Group Endpunkte
- [x] Time-Slot Endpunkte je Account
- [x] Post-from-Template Endpunkt
- [x] Quick-Schedule Endpunkt
- [x] Campaign Endpunkt
- [x] Reject plus Post-Listing Endpunkte

### Block D - Tests plus Doku
- [x] Unit-Tests fuer neue Services und Workflows
- [ ] API-nahe Kernpfade testen
- [x] README aktualisieren (neue Features plus API)
- [x] PROMPT_LOG aktualisieren

---

## Fortschrittsprotokoll (laufend aktualisiert)
- [x] Recherche von OSS-Tools im Social-Media-Manager-Bereich abgeschlossen.
- [x] Block A abgeschlossen.
- [x] Block B abgeschlossen.
- [x] Block C abgeschlossen.
- [ ] Block D abgeschlossen.

### Laufende Notiz
- API-nahe Tests sind als letzter offener Punkt markiert, konnten in dieser Umgebung aber noch nicht ausgefuehrt werden, da `python`/`pytest` nicht verfuegbar ist.
