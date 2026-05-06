"""Integration tests — apply DDL + load CSVs + verify counts and SCD2 behavior."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from student_warehouse.loader import (
    load_all,
    load_dim_courses,
    load_dim_schools,
    load_dim_student_scd2,
    load_fact_grades,
)

pytestmark = pytest.mark.integration


def _row_count(dsn: str, table: str) -> int:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def test_load_all_against_sample(fresh_warehouse: str, sample_dir: Path) -> None:
    counts = load_all(fresh_warehouse, sample_dir)

    assert counts["dim_school"] == 3
    assert counts["dim_course"] == 5
    assert counts["dim_student_v1_inserted"] == 80
    # v2 may close + reinsert ~16 students (about 20% changed in the seed generator)
    assert counts["dim_student_v2_inserted"] >= 1
    assert counts["dim_student_closed"] == counts["dim_student_v2_inserted"]
    assert counts["fact_grades"] >= 1

    assert _row_count(fresh_warehouse, "warehouse.dim_school") == 3
    assert _row_count(fresh_warehouse, "warehouse.dim_course") == 5


def test_dim_student_scd2_one_current_per_natural_key(
    fresh_warehouse: str, sample_dir: Path
) -> None:
    load_dim_student_scd2(fresh_warehouse, sample_dir / "students_v1.csv")
    load_dim_student_scd2(fresh_warehouse, sample_dir / "students_v2.csv")

    with psycopg.connect(fresh_warehouse) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT student_code, COUNT(*) FILTER (WHERE is_current)
            FROM warehouse.dim_student
            GROUP BY student_code
            HAVING COUNT(*) FILTER (WHERE is_current) <> 1
            """)
        violations = cur.fetchall()
    assert violations == []


def test_load_dim_courses_is_idempotent(fresh_warehouse: str, sample_dir: Path) -> None:
    load_dim_courses(fresh_warehouse, sample_dir / "courses.csv")
    load_dim_courses(fresh_warehouse, sample_dir / "courses.csv")  # second run = no-op
    assert _row_count(fresh_warehouse, "warehouse.dim_course") == 5


def test_load_dim_schools_is_idempotent(fresh_warehouse: str, sample_dir: Path) -> None:
    load_dim_schools(fresh_warehouse, sample_dir / "schools.csv")
    load_dim_schools(fresh_warehouse, sample_dir / "schools.csv")
    assert _row_count(fresh_warehouse, "warehouse.dim_school") == 3


def test_load_fact_grades_is_idempotent(fresh_warehouse: str, sample_dir: Path) -> None:
    load_dim_schools(fresh_warehouse, sample_dir / "schools.csv")
    load_dim_courses(fresh_warehouse, sample_dir / "courses.csv")
    load_dim_student_scd2(fresh_warehouse, sample_dir / "students_v1.csv")
    first = load_fact_grades(fresh_warehouse, sample_dir / "grades.csv")
    second = load_fact_grades(fresh_warehouse, sample_dir / "grades.csv")
    # second pass must insert 0 thanks to ON CONFLICT (grade_id) DO NOTHING
    assert second == 0
    assert first >= 1


def test_views_created_after_ddl(fresh_warehouse: str, sample_dir: Path) -> None:
    load_all(fresh_warehouse, sample_dir)
    # Apply analytics views and check at least one returns rows.
    views_sql = (
        Path(__file__).resolve().parents[2] / "sql" / "analytics" / "views.sql"
    ).read_text()
    with psycopg.connect(fresh_warehouse) as conn, conn.cursor() as cur:
        cur.execute(views_sql)
        cur.execute("SELECT COUNT(*) FROM warehouse.v_avg_grade_by_school")
        assert cur.fetchone()[0] == 3
        conn.commit()
