# syntax=docker/dockerfile:1.7
# Serveur MLflow (registre de modèles + suivi d'expériences), profil mlops.
# Base dédiée (mlflow-db), artefacts servis par MLflow lui-même vers le S3 compatible (Garage) :
# les clients (service ML, Airflow) n'ont besoin que de l'URL de suivi, jamais des clés S3.

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /usr/local/bin/
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH" \
    # boto3 en style « path » : Garage n'expose pas de sous-domaines par bucket
    AWS_CONFIG_FILE=/etc/aws-config
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv \
    && uv pip install --python /opt/venv/bin/python \
        "mlflow==3.17.2" "psycopg[binary]==3.3.6" "boto3==1.43.118"
COPY aws-config /etc/aws-config
RUN useradd --system --uid 1000 --create-home mlflow
USER mlflow
WORKDIR /home/mlflow
EXPOSE 5000
CMD ["sh", "-c", "exec mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri \"$MLFLOW_BACKEND_STORE_URI\" --artifacts-destination \"$MLFLOW_ARTIFACTS_DESTINATION\" --allowed-hosts \"$MLFLOW_ALLOWED_HOSTS\""]
