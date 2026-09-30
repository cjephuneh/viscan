# VIScan - AI interpreter for VIA cervical screening

Flask API that interprets VIA (acetic acid) cervical images with an OpenAI vision model and a
deterministic WHO-based rules engine. Returns a suspicious / not-suspicious verdict, lesion
findings, risk index, treatment eligibility and recommendation, and stores everything for
clinician review and outcome tracking.

Full API reference: [docs/API.md](docs/API.md)

## Repository layout

| Path | What |
|---|---|
| `app/`, `run.py` | Flask backend (API, AI interpreter, rules engine, database) |
| `frontend/` | Next.js clinician screening UI |
| `tests/` | Backend tests (pytest); frontend tests live in `frontend/tests/` |
| `docs/API.md` | API reference |
| `scripts/` | Dataset download and evaluation |

## Frontend

```bash
cd frontend
npm ci
npm run dev                 # http://127.0.0.1:3000
npm test
```

The UI calls `/api/v1/*` on its own origin; a Next.js route handler forwards those requests to
the Flask API, so the browser never needs the backend URL or API key.

| Variable (server-side) | Default | Description |
|---|---|---|
| `VISCAN_API_URL` | `http://127.0.0.1:5050` | Flask API base URL |
| `VISCAN_API_KEY` | – | Sent as `X-API-Key` when the API requires it |

Pages:

- `/` — patient welcome. Mia, an AI avatar ([Anam](https://docs.anam.ai/)), explains VIA
  screening, calms nervous patients (breathing exercise, concerns noted for the nurse), asks name,
  age, sex and the health questions, then shows a check-in code. Falls back to a short form if the
  avatar or microphone is unavailable.
- `/screening` — clinician workstation: checked-in patients (pre-filled visit details, nurse
  flags, anxiety change), visit details, AI reading, clinician confirmation, send results.
  `/screening?intake={id}` opens a specific check-in.
- `/care/{interpretation_id}` (map of nearby pharmacies from OpenStreetMap, partner hospitals with
referral, suggested supplies, send results by SMS/WhatsApp — messages are simulated for now).

## Run with Docker

```bash
cp .env.example .env        # add OPENAI_API_KEY, ANAM_API_KEY (and DB_* for Postgres)
docker compose up --build   # UI: http://localhost:3000 · API: http://localhost:5050
```

| Service | Image | Dockerfile | Port |
|---|---|---|---|
| `backend` | `viscan-backend` | `Dockerfile` (Flask + gunicorn) | 5050 |
| `frontend` | `viscan-frontend` | `frontend/Dockerfile` (Next.js standalone) | 3000 |

The frontend reaches the API at `http://backend:5050` inside the compose network. Without
`DB_HOST` (or `DATABASE_URL`), data is stored in SQLite on the `viscan-data` volume; set
`DATABASE_URL=sqlite:////data/viscan.db` in `.env` to force SQLite while `DB_*` is configured.

Browsers only allow microphone access (needed for the Mia avatar) on `https://` or `localhost`,
so put the frontend behind an HTTPS reverse proxy when deploying to a server.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python run.py               # http://localhost:5050
pytest -q
```

## Dataset evaluation (optional)

```bash
python scripts/malhari.py download --include-pap --per-label 4
python scripts/malhari.py evaluate --include-pap
```

Decision support only - a trained clinician must confirm every result.
