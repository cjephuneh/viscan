FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies (all packages have pre-compiled manylinux wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code and test suite
COPY . .
RUN chmod +x /app/docker-entrypoint.sh

# Expose port 9090 as required
EXPOSE 9090

# Native Python health check without requiring curl or apt-get
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import http.client; c = http.client.HTTPConnection('localhost', 9090, timeout=3); c.request('GET', '/health'); r = c.getresponse(); exit(0 if r.status == 200 else 1)"

# Entrypoint supporting test execution and server launch
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default: Start Uvicorn server on port 9090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9090"]
