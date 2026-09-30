# VISCAN Backend

## Flask Backend Technical Setup & Development Guide

VISCAN is an AI-assisted VIA cervical screening system. This repository contains the **Flask backend** responsible for the application API, database, VIA image handling, AI-service integration, clinician assessment, and selected external service integrations.

This document defines the backend setup and development structure for the current implementation.

---

## 1. Backend Scope

The VISCAN backend is responsible for:

- Screening records
- Facility records
- VIA image upload and storage metadata
- AI analysis integration
- AI result storage
- Clinician assessment records
- Maps integration
- SMS integration
- WhatsApp integration
- Language/translation integration
- Voice/avatar integration
- API validation
- Error handling
- Database migrations
- API documentation
- Automated testing

### Explicitly out of the current scope

The backend does **not** currently include:

- User management
- Login/authentication
- Role management
- User dashboards
- Complex patient management
- AI model training
- AI model development
- Direct frontend-to-AI communication

The frontend communicates with Flask. Flask communicates with the AI service and external services.

---

# 2. Architecture

```text
                         VISCAN FRONTEND
                               │
                               │ REST / JSON
                               ▼
                    ┌─────────────────────┐
                    │    FLASK BACKEND    │
                    │                     │
                    │ Screening API       │
                    │ Image API           │
                    │ AI API              │
                    │ Assessment API      │
                    │ Maps API            │
                    │ SMS API             │
                    │ WhatsApp API        │
                    │ Language API        │
                    │ Voice API            │
                    └──────────┬──────────┘
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
                 ▼             ▼             ▼
           PostgreSQL       AI Service   External APIs
           Docker           Flask/API    Maps/SMS/
                                          WhatsApp/
                                          Language/
                                          Voice
```

### Important architectural rule

The frontend should **not call the AI service directly**.

The correct flow is:

```text
Frontend
   ↓
VISCAN Flask API
   ↓
AI Service
   ↓
AI Model
   ↓
VISCAN Flask API
   ↓
Frontend
```

This keeps the AI implementation independent from the frontend.

---

# 3. Development Environment

The current development environment uses:

```text
Python       3.11.9
Framework    Flask
Database     PostgreSQL 16
Database     Docker container
Backend      Runs directly on Windows during development
```

Flask does **not** need to run inside Docker during the current development phase.

### Local architecture

```text
Windows
│
├── Python 3.11.9
│
├── Virtual Environment
│
├── Flask Backend
│
└── Docker Desktop
      │
      └── PostgreSQL
```

The Flask application connects to PostgreSQL through:

```text
localhost:5432
```

---

# 4. Project Structure

Recommended repository structure:

```text
VISCAN/
│
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── facility.py
│   │   ├── screening.py
│   │   ├── via_image.py
│   │   ├── ai_result.py
│   │   └── assessment.py
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── screening_routes.py
│   │   ├── image_routes.py
│   │   ├── ai_routes.py
│   │   ├── assessment_routes.py
│   │   ├── maps_routes.py
│   │   ├── notification_routes.py
│   │   ├── language_routes.py
│   │   └── voice_routes.py
│   │
│   ├── services/
│   │   ├── ai_service.py
│   │   ├── maps_service.py
│   │   ├── sms_service.py
│   │   ├── whatsapp_service.py
│   │   ├── language_service.py
│   │   └── voice_service.py
│   │
│   ├── schemas/
│   │   └── ...
│   │
│   └── utils/
│       └── ...
│
├── migrations/
├── tests/
├── uploads/
│   └── .gitkeep
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── docker-compose.yml
├── run.py
└── README.md
```

---

# 5. Python Environment

The project uses Python 3.11.

Verify:

```cmd
python --version
```

Expected:

```text
Python 3.11.9
```

Create a virtual environment:

```cmd
python -m venv venv
```

Activate it on Windows CMD:

```cmd
venv\Scripts\activate
```

Verify:

```cmd
python --version
```

---

# 6. Python Dependencies

The backend uses the following requirements.

```text
Flask
Flask-CORS
Flask-SQLAlchemy
Flask-Migrate
Flask-Smorest

psycopg[binary]

python-dotenv
requests
httpx
Pillow

marshmallow

pytest
pytest-flask

gunicorn
```

Install everything with:

```cmd
pip install -r requirements.txt
```

The `requirements.txt` file should remain the source of truth for backend dependencies.

---

# 7. Dependency Responsibilities

| Package | Purpose |
|---|---|
| Flask | Main backend framework |
| Flask-CORS | Frontend/backend cross-origin configuration |
| Flask-SQLAlchemy | SQLAlchemy integration |
| Flask-Migrate | Database migrations |
| Flask-Smorest | REST APIs and OpenAPI documentation |
| psycopg | PostgreSQL connection |
| python-dotenv | Environment variables |
| requests | External HTTP integrations |
| httpx | HTTP client for AI and external services |
| Pillow | Image validation/processing |
| marshmallow | Request/response validation |
| pytest | Automated tests |
| pytest-flask | Flask testing support |
| gunicorn | Production WSGI server |

---

# 8. PostgreSQL with Docker

PostgreSQL runs in Docker.

Create `docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16
    container_name: viscan_db
    restart: unless-stopped

    environment:
      POSTGRES_DB: viscan
      POSTGRES_USER: viscan_admin
      POSTGRES_PASSWORD: viscan_password

    ports:
      - "5432:5432"

    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Start the database:

```cmd
docker compose up -d
```

Check:

```cmd
docker ps
```

Stop the database:

```cmd
docker compose down
```

The PostgreSQL data is persisted through the Docker volume:

```text
postgres_data
```

---

# 9. Environment Variables

Create `.env` locally.

Example:

```env
FLASK_APP=run.py
FLASK_ENV=development

DATABASE_URL=postgresql+psycopg://viscan_admin:viscan_password@localhost:5432/viscan

AI_API_URL=http://localhost:8000

MAPS_API_KEY=
SMS_API_KEY=
WHATSAPP_API_KEY=
LANGUAGE_API_KEY=
VOICE_API_KEY=
```

Never commit `.env` to GitHub.

Create `.env.example` for the team:

```env
FLASK_APP=run.py
FLASK_ENV=development

DATABASE_URL=

AI_API_URL=

MAPS_API_KEY=
SMS_API_KEY=
WHATSAPP_API_KEY=
LANGUAGE_API_KEY=
VOICE_API_KEY=
```

---

# 10. Database Design

The current database should remain small and focused.

```text
Facility
   │
   └── Screening
          │
          ├── VIAImage
          │      │
          │      └── AIResult
          │
          └── Assessment
```

## Facility

Represents a health facility.

```text
id
name
type
is_active
created_at
updated_at
```

The initial project can contain:

```text
District Hospital
Health Centre
```

The database should still support additional facilities later.

---

## Screening

The central business entity.

```text
id
facility_id
patient_code
screening_date
status
created_at
updated_at
```

Example patient/study identifier:

```text
VIA-000001
```

The MVP should avoid collecting unnecessary personally identifiable information.

Suggested statuses:

```text
CREATED
IMAGE_UPLOADED
ANALYZED
REVIEWED
COMPLETED
```

---

## VIAImage

Stores the relationship between a screening and its VIA image.

```text
id
screening_id
file_path
uploaded_at
```

The actual image file should be stored in appropriate file/object storage. The database stores the file reference and metadata.

---

## AIResult

Stores the output from the AI service.

```text
id
via_image_id
prediction
confidence
model_version
processing_time_ms
created_at
```

Example:

```json
{
  "prediction": "abnormal",
  "confidence": 0.91,
  "model_version": "v1.0",
  "processing_time_ms": 842
}
```

AI results should be retained rather than overwritten so that future model versions can be evaluated.

---

## Assessment

Stores the clinician's assessment separately from the AI result.

```text
id
screening_id
result
notes
created_at
updated_at
```

Important:

```text
AI prediction != Clinician assessment
```

The AI provides decision support; the clinician's assessment remains a separate record.

---

# 11. API Versioning

All backend APIs should use:

```text
/api/v1/
```

Example:

```text
/api/v1/screenings/
```

This allows future API versions without immediately breaking existing frontend clients.

---

# 12. Core API Endpoints

## Health

```http
GET /api/v1/health/
```

Example response:

```json
{
  "status": "ok",
  "database": "connected"
}
```

---

## Screenings

```http
GET    /api/v1/screenings/
POST   /api/v1/screenings/
GET    /api/v1/screenings/{id}/
PATCH  /api/v1/screenings/{id}/
```

Create example:

```json
{
  "facility_id": 1,
  "patient_code": "VIA-000001"
}
```

---

## Images

```http
POST /api/v1/screenings/{id}/images/
GET  /api/v1/images/{id}/
```

The image endpoint should accept multipart form data.

Required validation:

- supported image format
- maximum file size
- valid screening
- valid file content
- safe file name/storage path

---

## AI

```http
POST /api/v1/screenings/{id}/analyze/
GET  /api/v1/ai-results/{id}/
```

The frontend calls the Django/Flask backend only.

---

## Assessment

```http
POST  /api/v1/screenings/{id}/assessment/
GET   /api/v1/screenings/{id}/assessment/
PATCH /api/v1/screenings/{id}/assessment/
```

---

# 13. AI Integration

The AI developer owns the AI model and AI inference API.

The Flask backend owns the integration.

```text
Frontend
   │
   ▼
POST /api/v1/screenings/15/analyze/
   │
   ▼
Flask
   │
   ├── Find screening
   ├── Find VIA image
   ├── Validate request
   │
   ▼
AI Service
   │
   ▼
AI Model
   │
   ▼
Prediction
   │
   ▼
Flask
   │
   ├── Validate AI response
   ├── Save AIResult
   └── Update screening status
   │
   ▼
Frontend
```

---

# 14. AI API Contract

The AI and backend developers must agree on the contract before integration.

Example request:

```http
POST /predict
Content-Type: application/json
```

```json
{
  "image_url": "https://storage.example/via/image-123.jpg",
  "image_id": 123
}
```

Example response:

```json
{
  "prediction": "abnormal",
  "confidence": 0.91,
  "model_version": "v1.0",
  "processing_time_ms": 842
}
```

The exact clinical prediction labels must be agreed upon by the clinical/research team.

The backend must not invent clinical labels.

---

# 15. AI Service Layer

AI API communication should live in:

```text
app/services/ai_service.py
```

Routes should remain thin.

Preferred structure:

```text
AI route
   ↓
AI service
   ↓
HTTP request
   ↓
AI API
   ↓
Validation
   ↓
AIResult
```

Do not put large amounts of external API logic directly into Flask route functions.

---

# 16. External Integrations

External integrations should follow the same service pattern.

```text
app/services/
│
├── ai_service.py
├── maps_service.py
├── sms_service.py
├── whatsapp_service.py
├── language_service.py
└── voice_service.py
```

The purpose is to keep provider-specific implementation separate from the core screening logic.

Example:

```text
Screening logic
      │
      └── NotificationService
              │
              ├── SMS provider
              └── WhatsApp provider
```

This makes it easier to change providers later.

---

# 17. Maps Integration

Maps should be exposed through a backend service rather than called directly from the frontend when API credentials or business logic are involved.

Potential functions:

```text
Find facility
Get facility coordinates
Calculate distance
Find nearby facility
```

Example API:

```http
GET /api/v1/maps/facilities/nearby?latitude=...&longitude=...
```

The exact map provider should be configured through environment variables.

---

# 18. SMS and WhatsApp

Notification functionality should be isolated from screening logic.

Possible endpoints:

```http
POST /api/v1/notifications/sms/
POST /api/v1/notifications/whatsapp/
```

The provider credentials must stay in `.env`.

Do not hard-code API keys.

---

# 19. Language Integration

The language service should provide a consistent backend interface.

Possible function:

```text
translate(text, source_language, target_language)
```

Potential endpoint:

```http
POST /api/v1/language/translate/
```

Example:

```json
{
  "text": "Screening completed",
  "source_language": "en",
  "target_language": "rw"
}
```

The actual supported languages and translation provider should be confirmed with the project requirements.

---

# 20. Voice / Avatar Integration

Voice or avatar functionality should be isolated in:

```text
app/services/voice_service.py
```

Possible responsibilities:

- text-to-speech
- speech-to-text
- voice response generation
- integration with the selected avatar/voice provider

Do not mix voice provider logic into screening or AI routes.

---

# 21. Error Handling

All APIs should return predictable errors.

Example:

```json
{
  "detail": "VIA image is required before analysis."
}
```

Common status codes:

```text
200 OK
201 Created
400 Bad Request
404 Not Found
409 Conflict
422 Unprocessable Entity
500 Internal Server Error
502 Bad Gateway
503 Service Unavailable
```

For an unavailable AI or external provider, the backend should return a controlled error rather than exposing internal exceptions.

---

# 22. Image Security

VIA images are sensitive project data.

The backend should implement:

- file type validation
- file size limits
- safe generated filenames
- restricted upload directories
- controlled image access
- no executable file uploads
- no secrets in image metadata/logs
- appropriate retention policy
- secure production storage

Never trust the uploaded filename or MIME type alone.

---

# 23. Database Migrations

Use Flask-Migrate.

Typical workflow:

```cmd
flask db init
flask db migrate -m "Initial database"
flask db upgrade
```

After changing a model:

```cmd
flask db migrate -m "Update screening model"
flask db upgrade
```

Migration files must be committed to GitHub.

Do not manually modify the production database schema without a migration.

---

# 24. Testing

Tests should cover the core workflow.

```text
Health check
     ↓
Create facility
     ↓
Create screening
     ↓
Upload VIA image
     ↓
Call AI integration
     ↓
Store AI result
     ↓
Create assessment
     ↓
Retrieve screening
```

Also test failures:

```text
Invalid image
Missing screening
Missing image
Invalid request
AI unavailable
AI returns invalid response
Database error
Invalid assessment
```

Run:

```cmd
pytest
```

---

# 25. Local Development

Start PostgreSQL:

```cmd
docker compose up -d
```

Activate Python environment:

```cmd
venv\Scripts\activate
```

Start Flask:

```cmd
python run.py
```

The backend should be available at:

```text
http://localhost:5000
```

Health check:

```text
http://localhost:5000/api/v1/health/
```

---

# 26. Git Structure

Recommended initial commits:

```text
Initial VISCAN Flask backend structure
Configure PostgreSQL with Docker
Add database models
Add database migrations
Add screening APIs
Add VIA image upload
Add AI integration
Add clinician assessment
Add external integrations
Add API documentation
Add backend tests
```

Use feature branches where practical:

```text
main
│
├── feature/screenings
├── feature/image-upload
├── feature/ai-integration
├── feature/assessments
├── feature/maps
├── feature/notifications
├── feature/language
└── feature/voice
```

---

# 27. Definition of Backend Completion

The backend implementation is considered ready for the first integrated VISCAN release when:

- Flask starts successfully.
- PostgreSQL runs through Docker.
- Flask connects to PostgreSQL.
- Database migrations work.
- Screening records can be created and retrieved.
- VIA images can be uploaded and validated.
- AI analysis can be requested through Flask.
- AI responses are validated and stored.
- Clinician assessments can be created and retrieved.
- External integrations are isolated into service modules.
- API documentation is available.
- Core workflow tests pass.
- Secrets are stored outside source control.
- The frontend can complete the intended workflow using the documented API.

---

# 28. Current Development Priority

Do not implement every integration at once.

Build the core first:

```text
1. Flask setup
       ↓
2. PostgreSQL + Docker
       ↓
3. Database models
       ↓
4. Migrations
       ↓
5. Screening API
       ↓
6. VIA image API
       ↓
7. AI integration
       ↓
8. AI result storage
       ↓
9. Clinician assessment
       ↓
10. Frontend integration
       ↓
11. Maps
       ↓
12. SMS / WhatsApp
       ↓
13. Language
       ↓
14. Voice / Avatar
       ↓
15. Testing + documentation
```

This keeps the core VISCAN workflow working while the additional integrations are developed independently.

---

# 29. Backend Principle

The backend should remain the **central integration layer**:

```text
                    ┌─────────────┐
                    │  FRONTEND   │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   VISCAN    │
                    │   FLASK     │
                    │   BACKEND   │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
    PostgreSQL          AI Service       External APIs
                         │              Maps / SMS /
                         ▼              WhatsApp /
                      AI Model          Language /
                                        Voice
```

The goal is not to make the backend unnecessarily large.

The goal is to make it **clear, modular, testable, and ready for the frontend and AI developers to integrate without depending on each other's internal implementation**.

---

# 30. VISCAN MVP Core

The essential product workflow remains:

```text
Create Screening
      ↓
Upload VIA Image
      ↓
Request AI Analysis
      ↓
Receive AI Result
      ↓
Store AI Result
      ↓
Clinician Assessment
      ↓
Complete Screening
```

Everything else should support this workflow rather than obscure it.
