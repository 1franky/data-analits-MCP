FROM python:3.12.13-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --no-cache-dir .

FROM base AS test

COPY tests ./tests
RUN pip install --no-cache-dir ".[dev]"

CMD ["pytest"]

FROM postgres:17.10-bookworm AS postgres-lab

COPY --chmod=0555 database/init/ /docker-entrypoint-initdb.d/

FROM base AS runtime

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --home-dir /app \
        --shell /usr/sbin/nologin app \
    && mkdir -p /app/data \
    && chown app:app /app/data

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2); raise SystemExit(0 if r.status == 200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
