FROM python:3.9-slim-bookworm

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG TORCH_WHEEL_URL=https://mirrors.aliyun.com/pytorch-wheels/cpu/torch-2.1.2%2Bcpu-cp39-cp39-linux_x86_64.whl
ARG TORCHVISION_WHEEL_URL=https://mirrors.aliyun.com/pytorch-wheels/cpu/torchvision-0.16.2%2Bcpu-cp39-cp39-linux_x86_64.whl

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install \
        --index-url "${PIP_INDEX_URL}" \
        "${TORCH_WHEEL_URL}" \
        "${TORCHVISION_WHEEL_URL}" \
    && python -m pip install \
        --index-url "${PIP_INDEX_URL}" \
        -r /app/requirements.txt \
    && python -m pip install \
        --index-url "${PIP_INDEX_URL}" \
        "numpy==1.26.4" "opencv-python==4.11.0.86" "ultralytics==8.3.209"

COPY backend /app/backend
COPY best.pt /app/best.pt

RUN mkdir -p /app/backend/uploads /app/backend/vector_db /app/backend/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=8s --start-period=180s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"

CMD ["sh", "-c", "cd /app/backend && alembic -c alembic.ini upgrade head && cd /app && exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --workers 1"]
