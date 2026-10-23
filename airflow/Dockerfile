# syntax=docker/dockerfile:1.7
# Airflow 3 (orchestration des DAG d'entraînement et de promotion), profil mlops.
# Image officielle, volontairement légère : pas de torch ici, l'entraînement tourne dans l'image
# `trainer` (ml/Dockerfile) lancée par l'opérateur Docker. MLflow est appelé par son API REST.

FROM apache/airflow:3.3.2-python3.12
USER airflow
RUN pip install --no-cache-dir "apache-airflow-providers-docker==4.6.1"
