FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY pyproject.toml ./
COPY backend/ ./backend/
RUN pip install --no-cache-dir -e . --no-deps --ignore-requires-python

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.app_factory:create_prod_app --factory --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --limit-concurrency 50 --timeout-keep-alive 30"]
