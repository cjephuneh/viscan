# ViScan AI Avatar Service (`ai-avatar`)

A high-performance FastAPI microservice that generates **interactive digital clinician avatars** (powered by **[Anam AI](https://anam.ai)**) for cervical cancer screening and colposcopy reporting.

This service ingests screening findings from the upstream ViScan backend, formats clinical narrative reports, persists data into a **remote PostgreSQL database**, and provisions real-time WebRTC avatar streaming sessions for clinicians.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    A["Upstream ViScan Backend\n(Cervical Scan Findings)"] -->|"POST /api/v1/reports"| B["ViScan AI Avatar Service\n(FastAPI • Port 9090)"]
    
    subgraph Core Processing
        B -->|"1. Format Spoken Script & System Prompt"| C["Clinical Formatter Engine"]
        B -->|"2. Save Report & Metadata"| D[("Remote PostgreSQL Database")]
        B -->|"3. POST /v1/auth/session-token"| E["Anam AI Cloud API"]
    end

    E -->|"Session Token (WebRTC)"| B
    B -->|"Store Token & Return Payload"| D

    subgraph Clinician Client / UI
        F["Clinician Frontend / Dashboard"] -->|"GET /api/v1/reports/{id}/session"| B
        F <==|"Direct Low-Latency WebRTC Stream"==> E
    end
```

---

## 🚀 Features

- **FastAPI Backend on Port 9090**: High-throughput async ASGI web server exposing interactive OpenAPI / Swagger documentation at `/docs`.
- **Anam AI Integration**: Server-to-server authentication with Anam AI (`https://api.anam.ai/v1`) using secure ephemeral session tokens (`POST /v1/auth/session-token`) so client apps never expose master API keys.
- **Remote PostgreSQL Support**: Asynchronous SQLAlchemy 2.0 with `asyncpg` connection pooling designed to connect directly to external/remote managed Postgres databases.
- **Clinical Cervical Formatter**: Translates colposcopy & screening indicators (Transformation Zone, Acetowhite changes, vascular morphology, Lugol's iodine uptake) into natural, medically accurate clinician narration and system prompts.
- **Production-Ready Docker**: Containerized with multi-stage build, health checks, and Docker Compose orchestration.

---

## 📂 Directory Structure

```text
ai-avatar/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── health.py        # Health & PostgreSQL connectivity checks
│   │       │   ├── personas.py      # Anam AI persona configurations
│   │       │   └── reports.py       # Cervical report creation & session tokens
│   │       └── router.py            # API v1 aggregated router
│   ├── core/
│   │   ├── config.py                # Pydantic BaseSettings (Port 9090, DB, Anam key)
│   │   └── database.py              # Async SQLAlchemy engine for remote Postgres
│   ├── models/
│   │   └── avatar_report.py         # SQLAlchemy ORM model for CervicalAvatarReport
│   ├── schemas/
│   │   └── avatar_report.py         # Pydantic validation schemas
│   ├── services/
│   │   ├── anam_service.py          # Anam AI API client
│   │   └── clinical_formatter.py    # Formatter for medical scripts & prompts
│   └── main.py                      # FastAPI app entrypoint
├── Dockerfile                       # Multi-stage image exposing port 9090
├── docker-compose.yml               # Docker Compose configuration
├── requirements.txt                 # Dependencies
├── .env.example                     # Environment template
└── README.md
```

---

## ⚙️ Configuration & Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Description | Default |
| :--- | :--- | :--- |
| `APP_PORT` | Port exposed by FastAPI | `9090` |
| `APP_HOST` | Host address | `0.0.0.0` |
| `ENVIRONMENT` | Environment (`development` or `production`) | `development` |
| `DATABASE_URL` | Remote PostgreSQL connection string (`postgresql+asyncpg://...`) | *Required* |
| `ANAM_API_KEY` | Your Anam AI API Key from [Anam Lab](https://anam.ai) | *Required for live avatar* |
| `ANAM_BASE_URL` | Anam API endpoint | `https://api.anam.ai/v1` |
| `ANAM_DEFAULT_PERSONA_ID` | Optional Anam Persona ID preset | `""` |
| `CORS_ORIGINS` | Permitted CORS origins (comma-separated or `*`) | `*` |

---

## 🏃 Quick Start

### Option A: Running with Docker (Recommended)

1. Make sure your `.env` is populated with your remote PostgreSQL `DATABASE_URL` and `ANAM_API_KEY`.
2. Build and start the container:

```bash
docker compose up --build -d
```

3. Verify logs:

```bash
docker compose logs -f ai-avatar
```

The service will be listening on `http://localhost:9090`.

---

### Option B: Running Locally with Python

1. Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the server on port 9090:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 9090 --reload
```

---

## 📡 API Reference

Interactive documentation is available at:
- Swagger UI: `http://localhost:9090/docs`
- ReDoc: `http://localhost:9090/redoc`

### 1. Ingest Report from Viscan Backend
**Endpoint:** `POST /api/v1/reports`

```bash
curl -X POST http://localhost:9090/api/v1/reports \
  -H "Content-Type: application/json" \
  -d '{
    "scan_id": "SCAN-2026-001",
    "patient_id": "PT-4421",
    "clinician_id": "DR-MWIMULE-01",
    "screening_result": "High-grade Squamous Intraepithelial Lesion (HSIL)",
    "confidence_score": 0.94,
    "findings": {
      "transformation_zone": "Type 1 - Fully visible",
      "aceto_white_changes": "Dense, opaque aceto-white lesion with distinct margins",
      "lesion_quadrant": "12 to 3 o clock",
      "vascular_patterns": "Coarse punctation and mosaicism",
      "lugol_iodine_reaction": "Schiller positive (mustard yellow uptake void)",
      "additional_observations": "No suspected invasion beyond squamocolumnar junction."
    },
    "recommendations": "Urgent colposcopic-directed punch biopsy and high-risk HPV genotyping."
  }'
```

---

### 2. Generate / Renew Anam WebRTC Session Token
**Endpoint:** `POST /api/v1/reports/{report_id_or_scan_id}/session`

Returns a short-lived session token (1 hour) for the clinician browser/app to start live avatar streaming:

```bash
curl -X POST http://localhost:9090/api/v1/reports/SCAN-2026-001/session
```

**Response:**
```json
{
  "report_id": "64bc0b3c-fa58-4509-9e8c-859a84a6fe0b",
  "session_token": "anam_sess_9a8f2...",
  "persona_id": null,
  "system_prompt": "You are Dr. ViScan...",
  "generated_script": "Hello. This is the automated ViScan clinical assessment report...",
  "expires_in_seconds": 3600,
  "instructions": "Pass this session_token to the Anam client SDK..."
}
```

---

### 3. List Reports
**Endpoint:** `GET /api/v1/reports?patient_id=PT-4421`

```bash
curl -X GET "http://localhost:9090/api/v1/reports"
```

---

### 4. Health Check
**Endpoint:** `GET /health` or `GET /api/v1/health`

```bash
curl -X GET "http://localhost:9090/health"
```

---

## 💻 Clinician Frontend Integration (Anam Web SDK)

In your clinician-facing web application (React, Vue, or Vanilla JS), use the session token returned by the `ai-avatar` backend to mount the interactive talking avatar:

```html
<!-- HTML Video Element -->
<video id="avatar-video" autoplay playsinline></video>
```

```javascript
import { createClient } from "@anam-ai/js-sdk";

async function launchClinicianAvatar(reportId) {
  // 1. Fetch fresh session token from the ai-avatar backend (port 9090)
  const res = await fetch(`http://localhost:9090/api/v1/reports/${reportId}/session`, {
    method: "POST"
  });
  const data = await res.json();
  const sessionToken = data.session_token;

  // 2. Initialize Anam client with session token (Zero API key exposure)
  const anamClient = createClient({ sessionToken });

  // 3. Stream real-time avatar video into DOM video element
  const videoElement = document.getElementById("avatar-video");
  await anamClient.streamToVideoElement(videoElement);

  // 4. (Optional) Instruct avatar to narrate report or handle clinician dialogue
  console.log("Avatar connected. Script:", data.generated_script);
}
```
