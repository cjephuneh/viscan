FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5050 \
    UPLOAD_DIR=/data/uploads \
    SQLITE_PATH=/data/viscan.db \
    GUNICORN_WORKERS=2 \
    GUNICORN_THREADS=4

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY run.py .

# Flask creates /app/instance at start-up, so the runtime user must own /app too.
RUN useradd --create-home --uid 1000 viscan \
    && mkdir -p /data/uploads /app/instance \
    && chown -R viscan:viscan /data /app
USER viscan
VOLUME ["/data"]

EXPOSE 5050

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/v1/health', timeout=4)"

# Vision-model calls can take 30-90 s, hence the long worker timeout.
CMD gunicorn "run:app" \
    --bind "0.0.0.0:${PORT}" \
    --workers "${GUNICORN_WORKERS}" \
    --threads "${GUNICORN_THREADS}" \
    --timeout 180 \
    --preload \
    --access-logfile -
