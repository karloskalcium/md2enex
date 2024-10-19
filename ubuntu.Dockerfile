FROM python:3.12.7-slim AS base
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
RUN apt-get update \
    && apt-get install -y make \
    && rm -rf /var/lib/apt/lists/*

FROM base AS builder
RUN pip install poetry
RUN python -m venv ./.venv
COPY ./pyproject.toml ./poetry.lock ./
RUN poetry install --only=main --no-root

COPY md2enex/ ./md2enex/
COPY Makefile README.md ./
COPY tests ./tests/
RUN poetry install --only-root
