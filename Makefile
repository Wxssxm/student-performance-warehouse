.PHONY: help install docker-up docker-down logs ddl seed load load-all metabase test lint format clean

help:
	@echo "Available targets:"
	@echo "  install      Create venv + install dev deps"
	@echo "  docker-up    Start postgres + metabase + auto-load data"
	@echo "  docker-down  Stop and remove all containers + volumes"
	@echo "  logs         Tail loader logs"
	@echo "  ddl          Apply DDL (idempotent: drops + recreates schema)"
	@echo "  seed         Seed dim_date for 2010-2030"
	@echo "  load         Load fact + dimensions from data/sample CSVs"
	@echo "  load-all     ddl + seed + load (full bootstrap)"
	@echo "  metabase     Provision Metabase database connection (after first boot)"
	@echo "  test         Run all tests with coverage"
	@echo "  lint         ruff + black checks"
	@echo "  format       Auto-fix lint and format"
	@echo "  clean        Remove venv and caches"

install:
	uv venv --python 3.11
	uv pip install -e ".[dev]"

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v

logs:
	docker compose logs -f loader

ddl:
	uv run student-warehouse apply-ddl

seed:
	uv run student-warehouse seed-dim-date --start 2010 --end 2030

load:
	uv run student-warehouse load

load-all: ddl seed load

metabase:
	uv run python metabase/setup.py

test:
	uv run pytest --cov=src/student_warehouse --cov-report=term-missing --cov-fail-under=70

lint:
	uv run ruff check .
	uv run black --check .

format:
	uv run ruff check --fix .
	uv run black .

clean:
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache .coverage htmlcov dist build
	find . -type d -name __pycache__ -exec rm -rf {} +
