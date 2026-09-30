# ViScan — AI-Powered Cervical Cancer Screening Platform

ViScan is an end-to-end clinical platform for AI-assisted cervical cancer screening (VIA digital colposcopy), patient intake, risk stratification, automated notification, and digital avatar clinical reporting.

---

## 📁 Repository Layout & Services

```
viscan/
├── frontend/             # Next.js 15 Clinician Screening & Patient Intake Workstation (Port 3000)
├── backend/              # Core Flask Screening API, PostgreSQL & Notification Worker (Port 8080)
├── ai-interpreter/       # VIA Cervical Screening AI Interpretation & Rules Engine (Port 5050)
├── ai-avatar/            # FastAPI Microservice: Clinical Video Reporting via Anam AI (Port 9090)
├── docker-compose.yml    # Master multi-service deployment orchestrator
└── README.md             # Unified Platform Documentation
```

| Component | Directory | Framework / Stack | Port | Primary Responsibility |
|---|---|---|---|---|
| **Frontend** | [`frontend/`](./frontend) | Next.js 15, TypeScript, Tailwind | `3000` | Clinician workstation, patient check-in, Mia avatar streaming, and care referral maps. |
| **Core Backend** | [`backend/`](./backend) | Python 3.11, Flask, PostgreSQL | `8080` | Patient screening records, image queues, SMS/WhatsApp notifications, facility locator. |
| **AI Interpreter** | [`ai-interpreter/`](./ai-interpreter) | Flask, OpenAI Vision, WHO Rules | `5050` | Evaluates acetic acid images, identifies lesions, calculates SWEDE scores & risk indices. |
| **AI Avatar** | [`ai-avatar/`](./ai-avatar) | FastAPI, Async SQLAlchemy, Anam AI | `9090` | Generates direct playable MP4 clinician video reports and HTML5 interactive video player. |

---

## 🚀 Quick Start Guide

### 1. Unified Multi-Service Launch (Docker Compose)
To launch all services together from the repository root:
```bash
docker compose up --build -d
```
- **Frontend UI**: `http://localhost:3000`
- **AI Interpreter**: `http://localhost:5050`
- **AI Avatar Service**: `http://localhost:9090`

---

### 2. Standalone Service Guides

#### Frontend ([`frontend/`](./frontend))
```bash
cd frontend
npm ci
npm run dev                 # http://localhost:3000
npm test
```
- `/` — Patient welcome screen featuring Mia, an Anam AI avatar guiding patients through intake and breathing exercises.
- `/screening` — Clinician workstation for review, AI diagnostic confirmation, and assessment. "Walk me through this with Kezia" docks the AI clinical coach next to any reading.
- `/screenings` — Past screenings: every AI reading with the confirmed result, risk, follow-up date and whether the patient was referred, messaged or used for coaching. Search by patient ID, name, site or `#reading`, filter by verdict, review status, dates, referred or overdue, and sort by date or risk. Expand a row for the annotated image, the recommendation and links to the report, care page and a Kezia lesson on that case (`/learn?case=<id>`).
- `/learn` — Training with Kezia, an Anam AI clinical coach: pick a past reading or a practice lesson; she highlights parts of the result, traces lesions on a cervix clock face, builds an action plan, quizzes you (scored) and role-plays the patient so you can rehearse counselling. Lessons are kept as a training record.
- `/care/{id}` — Care map, nearby pharmacies from OpenStreetMap, and partner hospital referrals.

#### Core Backend ([`backend/`](./backend))
```bash
cd backend
cp .env.example .env
docker compose up -d        # Starts PostgreSQL on port 5432
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
flask db upgrade            # Apply Alembic schema migrations
python run.py               # http://localhost:8080
```
- API Docs: `http://localhost:8080/api/v1/docs`
- Health: `http://localhost:8080/api/v1/health/`

#### AI Interpreter ([`ai-interpreter/`](./ai-interpreter))
```bash
cd ai-interpreter
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python run.py               # http://localhost:5050
pytest -q
```
- Standalone Docker: `cd ai-interpreter && docker compose up --build`
- Full API reference: [`ai-interpreter/docs/API.md`](./ai-interpreter/docs/API.md)

#### AI Avatar Microservice ([`ai-avatar/`](./ai-avatar))
```bash
cd ai-avatar
cp .env.example .env
# Run with Docker:
docker compose up --build -d ai-avatar     # http://localhost:9090
# Run automated test suite:
docker compose run --rm test
```
- Swagger Docs: `http://localhost:9090/docs`
- Video Player: `http://localhost:9090/player/{report_id}`
- Integration Guide: [`ai-avatar/FRONTEND_API_GUIDE.md`](./ai-avatar/FRONTEND_API_GUIDE.md)

---

## 🧪 Testing

- **Frontend Tests**: `cd frontend && npm test`
- **Core Backend Tests**: `cd backend && python -m pytest`
- **AI Interpreter Tests**: `cd ai-interpreter && python -m pytest`
- **AI Avatar Tests**: `cd ai-avatar && python -m pytest` (live Anam tests run only with `ANAM_LIVE_TESTS=1`)

All four suites run in GitHub Actions on every push and pull request ([`.github/workflows/ci.yml`](./.github/workflows/ci.yml)).

---

## 🚢 Production Deployment (Nginx gateway on `gp5`)

Production runs from [`docker-compose.prod.yml`](./docker-compose.prod.yml): an **Nginx gateway on port 80** is the only public
entrypoint and routes to the four services (see [`nginx/nginx.conf`](./nginx/nginx.conf)):

| Path | Service |
|---|---|
| `/`, everything not below | frontend |
| `/api/v1/*` (interpret, intake, interpretations, images/&lt;id&gt;/file, avatar, coach, worklist, `/api/v1/screenings` without trailing slash, …) | ai-interpreter |
| `/api/v1/{facilities,screenings,analysis-queue,analysis-jobs,ai-results,maps,notifications,language,voice}/`, `/api/v1/health/`, `/api/v1/docs`, `/api/v1/backend-images/<id>/file` | backend |
| `/api/v1/reports`, `/api/v1/personas`, `/player/*` | ai-avatar |

VIA images are stored in the S3-compatible **MinIO** bucket `via-images` (prefixes `interpreter/` and `backend/`), configured through
`S3_*` in the root `.env` (see [`.env.example`](./.env.example)). Without `S3_ENDPOINT` the services fall back to local disk.

**How a deploy happens** (no secrets are stored in GitHub):

1. Push to `main` → GitHub Actions runs all test suites.
2. On the server a systemd timer runs [`scripts/server-deploy.sh`](./scripts/server-deploy.sh) every 2 minutes. When it sees a new
   commit on `origin/main` whose CI check *"all tests passed"* is green, it pulls it and runs `docker compose -f docker-compose.prod.yml up --build -d`,
   then health-checks the gateway. A red CI run is never deployed.
3. Logs: `ssh gp5 tail -f ~/.viscan-deploy/deploy.log` or `journalctl -u viscan-deploy.service`.

One-time server setup: clone the repo to `/home/ubuntu/viscan`, create `.env`, `ai-interpreter/.env`, `ai-avatar/.env`, `backend/.env`
from their `.example` files, then `sudo ./scripts/install-server-deployer.sh`.
Manual deploy / env sync from a laptop: `./scripts/deploy.sh` (`--env-only` to only copy env files).

---

*Decision support only — a certified clinician must confirm every automated result.*
