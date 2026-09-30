# VISCAN Flask Backend

AI-assisted VIA cervical screening API. The frontend talks to this Flask service only; Flask talks to PostgreSQL, the AI service, and external providers.

## Requirements

- Python 3.11
- Docker, for PostgreSQL 16. The Flask app itself runs on the host.

The Flask service lives in this `backend` directory.

## Quick start

From the repository root:

```cmd
cd backend
docker compose up -d
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`.env.example` already points at the Docker database on `localhost:5432`. Secrets stay in `.env` only (never commit it).

Start the API on port **8080**:

```cmd
python run.py
```

- API index: `http://localhost:8080/api/v1/`
- Health: `http://localhost:8080/api/v1/health/`
- OpenAPI / Swagger UI: `http://localhost:8080/api/v1/docs`

Listen address is `0.0.0.0:8080` so other machines on the network can reach the backend during integration.

## Database

PostgreSQL runs in Docker. Flask runs on the host and connects through `DB_*` in `.env` (`localhost`, port `5432`, database `viscan`, SSL off). The container publishes that port; the API is not inside Docker.

`docker compose up -d` starts only the database. Apply the schema from the host with `flask db upgrade`.

The chain below is the schema history. Apply it with `flask db upgrade`.

### How each phase is committed

The chain is linear and applied on the Docker database from the host, so there is one Alembic head and revisions do not fork.

Each phase is one file in `migrations/versions/` and one git commit. `down_revision` is always the previous phase's revision id.

For each phase:

1. Add only that phase's revision file.
2. Commit that file by itself, using the commit message in the table.
3. Apply it on the Docker database from the host:

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
| 11 | `011_analysis_jobs` | `analysis_jobs` queue, one processing job and one active job per image | add analysis jobs queue |

Phase 10 is the data migration for the two starter facilities. `flask seed-facilities` remains for resetting a local database.

## Core workflow APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health/` | Health + DB connectivity |
| GET/POST | `/api/v1/facilities/` | Facilities |
| GET/POST | `/api/v1/screenings/` | List / create screenings |
| GET/PATCH | `/api/v1/screenings/{id}/` | Screening detail / update |
| POST | `/api/v1/screenings/{id}/images/` | Multipart VIA image upload (`file`). Stores the file and places it on the analysis queue. |
| GET | `/api/v1/images/{id}/` | Image metadata, including its queue job |
| GET | `/api/v1/images/{id}/file` | Image bytes |
| POST | `/api/v1/screenings/{id}/analyze/` | Queue the latest image. Returns `202` and the job. If that image is already queued or processing, returns the same job. |
| GET | `/api/v1/analysis-queue/` | The image being analyzed, images waiting, and recently finished jobs |
| GET | `/api/v1/analysis-jobs/{id}/` | One job. Poll until `completed` or `failed`; `ai_result` is set when analysis finishes. |
| GET | `/api/v1/ai-results/{id}/` | Stored AI result |
| POST/GET/PATCH | `/api/v1/screenings/{id}/assessment/` | Clinician assessment |
| GET | `/api/v1/maps/facilities/nearby` | Nearby facilities |
| POST | `/api/v1/notifications/sms/` | SMS stub until provider keys are set |
| POST | `/api/v1/notifications/whatsapp/` | WhatsApp stub |
| POST | `/api/v1/language/translate/` | Translation stub |
| POST | `/api/v1/voice/synthesize/` | Voice stub |

Errors use a consistent body: `{"detail": "..."}`.

## Analysis queue

Uploading an image does not wait for the AI service. The API stores the file, inserts an `analysis_jobs` row with status `queued`, and returns. A worker inside the API process then takes the oldest queued image, marks it `processing`, calls the AI service, and only then takes the next image.

While one image is `processing`, further uploads stay in `queued` with `ahead` set to how many images must finish first. `GET /api/v1/analysis-queue/` is the live view of that line. The database allows only one `processing` row, so a second API process cannot run a second analysis at the same time.

Screening status follows the queue: `QUEUED`, then `ANALYZING`, then `ANALYZED` or `ANALYSIS_FAILED`. A failed job does not block the images behind it. `POST .../analyze/` queues the latest image again after a failure.

The worker starts with the API. Set `QUEUE_WORKER_ENABLED=false` to leave jobs queued until something else calls the worker. A processing job that outlives the AI timeout is put back on the queue, and after `QUEUE_MAX_ATTEMPTS` it is marked failed so the line cannot stall.

## Tests

```cmd
pytest
```

Tests use an in-memory SQLite database and do not require PostgreSQL.

## Project layout

Paths below are inside `backend/`.

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
