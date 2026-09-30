# ViScan — AI-Powered Cervical Cancer Screening & Clinical Reporting

ViScan is an advanced clinical platform for AI-assisted cervical cancer screening, digital colposcopy, and automated clinical reporting.

---

## 📁 Repository Structure

- [**`ai-avatar/`**](./ai-avatar) — FastAPI microservice generating interactive digital clinician avatars (powered by **[Anam AI](https://anam.ai)**) and pre-rendered MP4 clinical reporting videos.
  - [**`ai-avatar/README.md`**](./ai-avatar/README.md) — Service overview, local/docker setup, and API documentation.
  - [**`ai-avatar/FRONTEND_API_GUIDE.md`**](./ai-avatar/FRONTEND_API_GUIDE.md) — Complete API payload contracts, JSON responses, and frontend integration code (React / HTML5 video / WebRTC).

---

## 🚀 Services Overview

### 1. AI Avatar Microservice (`ai-avatar`)
- **Port:** `9090`
- **Framework:** FastAPI (Python 3.12, Async SQLAlchemy 2.0, Uvicorn)
- **Database:** Remote PostgreSQL (`app_db`)
- **Avatar Engine:** Anam AI (`https://api.anam.ai/v1`)
- **Key Features:**
  - Ingests cervical colposcopy findings (Transformation Zone, Acetowhite changes, vascular morphology, Lugol iodine uptake).
  - Translates visual findings into natural, professional clinical narration scripts.
  - Asynchronously renders downloadable and playable `.mp4` video URLs.
  - Serves an out-of-the-box responsive clinical video player page (`/player/{id}`).
  - Provides WebRTC streaming session tokens for real-time two-way dialogue with the digital avatar.
  - Fully containerized with Docker & Docker Compose.
  - 100% test coverage with automated `pytest` test suite (22 tests).

---

## 🏃 Quick Start (`ai-avatar`)

### 1. Environment Configuration
Navigate to `ai-avatar/` and configure `.env`:

```bash
cd ai-avatar
cp .env.example .env
```

Ensure your `.env` contains:
```env
APP_PORT=9090
DATABASE_URL=postgresql+asyncpg://dev_user:DevTeam2026_GlobalAccess@16.192.134.200:5432/app_db
ANAM_API_KEY=your_anam_api_key_here
```

### 2. Run with Docker Compose
```bash
cd ai-avatar
docker compose up --build -d
```

### 3. Run Locally with Python
```bash
cd ai-avatar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 9090 --reload
```

Interactive OpenAPI Swagger documentation will be available at:
👉 **`http://localhost:9090/docs`**

---

## 🧪 Running Automated Tests

```bash
cd ai-avatar
source .venv/bin/activate
pytest -v
```

---

## 📖 Documentation Links

- [AI Avatar Service README](./ai-avatar/README.md)
- [Frontend Integration Guide & API Contracts](./ai-avatar/FRONTEND_API_GUIDE.md)
