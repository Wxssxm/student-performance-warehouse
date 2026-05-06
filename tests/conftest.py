"""Pytest fixtures for unit + integration tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from student_warehouse.config import reset_settings
from student_warehouse.ddl import apply_ddl
from student_warehouse.loader import seed_dim_date

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"


@pytest.fixture(autouse=True)
def _reset_settings() -> Iterator[None]:
    reset_settings()
    yield
    reset_settings()


@pytest.fixture(scope="session")
def sample_dir() -> Path:
    return SAMPLE_DIR


def _postgres_available() -> bool:
    return os.environ.get("POSTGRES_HOST") is not None and os.environ.get("CI") is not None


@pytest.fixture(scope="session")
def dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "warehouse")
    password = os.environ.get("POSTGRES_PASSWORD", "warehouse_dev_only")
    db = os.environ.get("POSTGRES_DB", "student_warehouse")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@pytest.fixture
def fresh_warehouse(dsn: str) -> Iterator[str]:
    """Apply DDL + seed dim_date for the integration session, then truncate."""
    if not _postgres_available():
        pytest.skip("Postgres-dependent integration test")
    apply_ddl(dsn)
    seed_dim_date(dsn, 2024, 2026)
    try:
        yield dsn
    finally:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE warehouse.fact_grades RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE warehouse.dim_student RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE warehouse.dim_course RESTART IDENTITY CASCADE")
                cur.execute("TRUNCATE warehouse.dim_school RESTART IDENTITY CASCADE")
            conn.commit()
