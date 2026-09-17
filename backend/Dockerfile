FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app
RUN pip install --no-cache-dir uv==0.9.10
COPY pyproject.toml uv.lock ./

FROM base AS development
RUN uv sync --frozen --dev
COPY . .
EXPOSE 8000

FROM base AS production
RUN uv sync --frozen --no-dev
COPY . .
USER nobody
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
