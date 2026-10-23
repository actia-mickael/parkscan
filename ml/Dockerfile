# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /usr/local/bin/
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    # Caches des modèles génériques (YOLO véhicule, OCR) : remplis au build, partagés par tous les utilisateurs
    HOME=/opt/home \
    XDG_CACHE_HOME=/opt/home/.cache \
    YOLO_CONFIG_DIR=/opt/home/.config/Ultralytics \
    ML_GENERIC_MODELS_DIR=/opt/models \
    ML_WEIGHTS_DIR=/app/weights
# libgl1 et libglib2.0 : exigés par opencv-python (dépendance d'ultralytics) ; curl : healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/home /opt/models
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra dev
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra dev \
    && python -m parkscan_ml.prefetch
CMD ["uvicorn", "parkscan_ml.main:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]

FROM base AS prod
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev \
    && python -m parkscan_ml.prefetch \
    && useradd --system --uid 1000 app \
    && chown -R app:app /app /opt/venv /opt/home /opt/models
USER app
CMD ["uvicorn", "parkscan_ml.main:app", "--host", "0.0.0.0", "--port", "8002"]
