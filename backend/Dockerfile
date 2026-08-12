# ── RoadSense AI — Backend Dockerfile ────────────────────────────────────────
FROM python:3.11-slim

# ── System packages & Memory limits ──────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    PYTHONUNBUFFERED=1 \
    MALLOC_TRIM_THRESHOLD_=100000

RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libgl1 libsm6 libxext6 libxrender-dev \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
# Install CPU-only PyTorch FIRST to prevent installing 2.5GB CUDA packages (saves 400MB RAM)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# ── App code ───────────────────────────────────────────────────────────────
COPY . /app/

# ── Runtime directories ────────────────────────────────────────────────────
RUN mkdir -p /data/videos /data/outputs /app/static

# ── Environment defaults ───────────────────────────────────────────────────
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
CMD ["sh", "-c", "python3 -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips=*"]
