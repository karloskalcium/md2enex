FROM python:3.14.3-slim AS base
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH="/app/.venv/bin:$PATH"

FROM base AS builder
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --no-dev --no-install-project

COPY md2enex/ ./md2enex/
COPY README.md ./
RUN uv sync --no-dev
