.PHONY: dev down check backend-install backend-check frontend-install frontend-check

dev:
	docker compose up --build

down:
	docker compose down

backend-install:
	cd backend && uv sync --dev

backend-check:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd backend && uv run mypy app
	cd backend && uv run pytest

frontend-install:
	cd frontend && npm ci

frontend-check:
	cd frontend && npm run lint
	cd frontend && npm run test:ci
	cd frontend && npm run build

check: backend-check frontend-check
	docker compose config --quiet
