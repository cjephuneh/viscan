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
- `/screening` — Clinician workstation for review, AI diagnostic confirmation, and assessment.
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
- **Core Backend Tests**: `cd backend && pytest`
- **AI Interpreter Tests**: `cd ai-interpreter && pytest tests/test_api.py`
- **AI Avatar Tests**: `cd ai-avatar && pytest -v` (or `docker compose run --rm test`)

---

*Decision support only — a certified clinician must confirm every automated result.*
