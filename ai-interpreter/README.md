# VIScan — AI Interpreter for VIA Cervical Screening

Flask API that interprets VIA (acetic acid) cervical images with a local vision model and a deterministic WHO-based rules engine. Returns a suspicious / not-suspicious verdict, lesion findings, risk index, treatment eligibility and recommendation, and stores everything for clinician review and outcome tracking.

Full API reference: [docs/API.md](docs/API.md)

## Repository layout

| Path | What |
|---|---|
| `app/`, `run.py` | Flask backend (API, AI interpreter, rules engine, database) |
| `tests/` | Backend tests (pytest) |
| `docs/API.md` | API reference |
| `AGENTS.md` | Port boundary other coding agents must keep |
| `scripts/` | Dataset download, evaluation, and the model server |
| `notebooks/viscan_colab.ipynb` | One GPU runtime for the model server. The app only needs its URL |

## Run with Docker

```bash
cp .env.example .env        # add ANAM_API_KEY (and DB_* for Postgres)
docker compose up --build   # http://localhost:5050
```

Without `DB_HOST`, data is stored in SQLite on the `viscan-interpreter-data` volume.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-model.txt
python scripts/pull_model.py
python run.py               # http://localhost:5050
pytest -q
```

`INTERPRETER_MODE=auto` uses `models/base` when those weights are present. After `scripts/finetune_via.py` writes `models/viscan-via-adapter`, that adapter is loaded on top of the base weights. With no weights on disk the colour heuristic is the fallback.

## Run the model on another machine

The API asks an interpreter for a VIA JSON result. It does not contain Colab, Kaggle, or GPU code. `INTERPRETER_MODE=remote` sends the image to whatever URL is serving `scripts/model_server.py`.

Colab is one way to start that server. Open `notebooks/viscan_colab.ipynb` there (T4 GPU), upload a zip of this folder without `.venv` and `models`, and run the cells. Paste the three lines it prints into `.env` and restart `python run.py`:

```bash
INTERPRETER_MODE=remote
REMOTE_MODEL_URL=https://the-gpu-host
REMOTE_MODEL_TOKEN=the-token-from-that-runtime
```

The same server command runs on Kaggle or a VM. Changing the URL is the whole switch. A free Colab URL changes every time that session restarts. The token is what closes the tunnel, so use it for test images.

## Dataset evaluation (optional)

```bash
python scripts/malhari.py download --include-pap --per-label 4
python scripts/malhari.py evaluate --include-pap
```

*Decision support only — a trained clinician must confirm every result.*
