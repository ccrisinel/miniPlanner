# syntax=docker/dockerfile:1

# --- build the environment ---------------------------------------------------
FROM python:3.13-alpine AS build

COPY --from=ghcr.io/astral-sh/uv:0.12.12 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first: this layer is only rebuilt when the lock changes.
# LICENSE and README are read by the build backend during the next step.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --extra prod --no-install-project

# Then the project itself, installed as a real package: templates and static
# files included.
COPY src ./src
RUN uv sync --frozen --no-dev --extra prod --no-editable

# --- final image -------------------------------------------------------------
FROM python:3.13-alpine AS runtime

RUN adduser -D -u 10001 planner && mkdir -p /data && chown planner:planner /data

COPY --from=build --chown=planner:planner /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    MINIPLANNER_DB=/data/planner.db

USER planner
WORKDIR /app
EXPOSE 8000
VOLUME /data

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/').read()"

# gthread rather than extra processes: SQLite is happier with few writers.
CMD ["gunicorn", "miniplanner:create_app()", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", "--worker-class", "gthread", "--threads", "4", \
     "--access-logfile", "-"]
