FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.9.22 /uv /uvx /bin/
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"
RUN useradd -m -u 1000 paidiver
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups

FROM base AS development
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group lint --group test
COPY --chown=paidiver:paidiver . .
RUN python manage.py collectstatic --noinput && chown -R paidiver:paidiver /app
USER paidiver
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]

FROM base AS runtime
COPY --chown=paidiver:paidiver . .
RUN python manage.py collectstatic --noinput && chown -R paidiver:paidiver /app
USER paidiver
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
