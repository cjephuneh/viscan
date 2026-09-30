# VISCAN Flask Backend

AI-assisted VIA cervical screening API. The frontend talks to this Flask service only; Flask talks to PostgreSQL, the AI service, and external providers.

## Requirements

- Python 3.11
- PostgreSQL 16 (shared remote development database)

## Quick start

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with the shared PostgreSQL host, user, password, and `DB_SSLMODE=disable`. Secrets stay in `.env` only (never commit it).

Start the API on port **8080**:

```cmd
python run.py
```

- API base: `http://localhost:8080/api/v1/`
- Health: `http://localhost:8080/api/v1/health/`
- OpenAPI / Swagger UI: `http://localhost:8080/api/v1/docs`

Listen address is `0.0.0.0:8080` so other machines on the network can reach the backend during integration.

## Database

Development uses the remote PostgreSQL host configured via `DB_*` in `.env` (host `16.192.134.200`, port `5432`, SSL off). Set `DB_SSLMODE=disable` before connecting. Optional local Docker Postgres is available in `docker-compose.yml` if you need an isolated database and port `5432` is free.

The shared database already contains `cervical_avatar_reports`. These phases add the VISCAN tables beside it and leave that table unchanged.

The chain below is the schema history. Apply it with `flask db upgrade`.

### How each phase is committed

The chain is linear and applied on the real database, so there is one Alembic head and revisions do not fork.

Each phase is one file in `migrations/versions/` and one git commit. `down_revision` is always the previous phase's revision id.

For each phase:

1. Add only that phase's revision file.
2. Commit that file by itself, using the commit message in the table.
3. Apply it on the real database:

```cmd
flask db upgrade
```

4. Start the next phase only after that commit and that upgrade have succeeded.

A revision that is already committed and upgraded stays as written. Later work is a new phase at the end of the chain.

### Phases

| Phase | Revision | What it adds | Commit message |
|-------|----------|--------------|----------------|
| 1 | `001_facilities` | `facilities`: name, type, `is_active`, timestamps | add facilities table |
| 2 | `002_facility_coordinates` | `latitude` and `longitude` on `facilities` | add facility coordinates |
| 3 | `003_screenings` | `screenings`, foreign key to `facilities`, unique `patient_code`, status default `CREATED` | add screenings table |
| 4 | `004_screening_status_index` | index `ix_screenings_facility_status` on (`facility_id`, `status`) | index screenings by facility and status |
| 5 | `005_via_images` | `via_images`, foreign key to `screenings`, unique `file_path`, media type, size, `uploaded_at` | add via images table |
| 6 | `006_via_image_index` | index `ix_via_images_screening_id` | index via images by screening |
| 7 | `007_ai_results` | `ai_results`, foreign key to `via_images`, prediction, confidence, model version, processing time | add ai results table |
| 8 | `008_ai_result_index` | index `ix_ai_results_via_image_id` | index ai results by image |
| 9 | `009_assessments` | `assessments`, one row per screening | add clinician assessments |
| 10 | `010_seed_facilities` | District Hospital and Health Centre, inserted only when missing | seed starter facilities |

Phase 10 is the data migration for the two starter facilities. `flask seed-facilities` remains for resetting a local database.

## Core workflow APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health/` | Health + DB connectivity |
| GET/POST | `/api/v1/facilities/` | Facilities |
| GET/POST | `/api/v1/screenings/` | List / create screenings |
| GET/PATCH | `/api/v1/screenings/{id}/` | Screening detail / update |
| POST | `/api/v1/screenings/{id}/images/` | Multipart VIA image upload (`file`) |
| GET | `/api/v1/images/{id}/` | Image metadata |
| GET | `/api/v1/images/{id}/file` | Image bytes |
| POST | `/api/v1/screenings/{id}/analyze/` | Call AI service via Flask |
| GET | `/api/v1/ai-results/{id}/` | Stored AI result |
| POST/GET/PATCH | `/api/v1/screenings/{id}/assessment/` | Clinician assessment |
| GET | `/api/v1/maps/facilities/nearby` | Nearby facilities |
| POST | `/api/v1/notifications/sms/` | SMS stub until provider keys are set |
| POST | `/api/v1/notifications/whatsapp/` | WhatsApp stub |
| POST | `/api/v1/language/translate/` | Translation stub |
| POST | `/api/v1/voice/synthesize/` | Voice stub |

Errors use a consistent body: `{"detail": "..."}`.

## Tests

```cmd
pytest
```

Tests use an in-memory SQLite database and do not require PostgreSQL.

## Project layout

```text
app/
  models/
  routes/
  services/
  schemas/
  utils/
migrations/
tests/
uploads/
run.py
```
