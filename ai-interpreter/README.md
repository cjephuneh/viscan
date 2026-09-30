# VIScan — AI Interpreter for VIA Cervical Screening

Flask API that interprets VIA (acetic acid) cervical images with an OpenAI vision model and a deterministic WHO-based rules engine. Returns a suspicious / not-suspicious verdict, lesion findings, risk index, treatment eligibility and recommendation, and stores everything for clinician review and outcome tracking.

Full API reference: [docs/API.md](docs/API.md)

## Repository layout

| Path | What |
|---|---|
| `app/`, `run.py` | Flask backend (API, AI interpreter, rules engine, database) |
| `tests/` | Backend tests (pytest) |
| `docs/API.md` | API reference |
| `scripts/` | Dataset download and evaluation |

## Run with Docker

```bash
cp .env.example .env        # add OPENAI_API_KEY, ANAM_API_KEY (and DB_* for Postgres)
docker compose up --build   # http://localhost:5050
```

Without `DB_HOST`, data is stored in SQLite on the `viscan-interpreter-data` volume.

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

*Decision support only — a trained clinician must confirm every result.*
