# ── RoadSense AI — Dockerfile ──────────────────────────────────────────────
# Multi-stage: deps → runtime. GPU (CUDA) is optional via runtime flag.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# ── System packages ────────────────────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libgl1 libsm6 libxext6 libxrender-dev \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*


# ── Python dependencies ────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── App code ───────────────────────────────────────────────────────────────
COPY backend/ /app/

# ── Runtime directories ────────────────────────────────────────────────────
# Videos + DB are mounted as Docker volumes so data persists across restarts
RUN mkdir -p /data/videos /data/outputs /app/static

# ── Environment defaults (override in docker-compose or .env) ─────────────
ENV VIDEOS_DIR=/data/videos \
    OUTPUTS_DIR=/data/outputs \
    DATABASE_URL=sqlite+aiosqlite:///data/roadsense.db \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

# ── Health check ───────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/stats/overview')" || exit 1

# ── Entrypoint ─────────────────────────────────────────────────────────────
CMD ["python3", "-m", "uvicorn", "main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
