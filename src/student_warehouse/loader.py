"""Idempotent loader for the star schema.

Strategy:
- dim_date: generate rows for a date range and INSERT ... ON CONFLICT DO NOTHING.
- dim_school / dim_course: UPSERT on natural key, in-place update (Type 1).
- dim_student: SCD Type 2. For each natural key, compare incoming attributes
  with the current row; if they differ, close the current row (set valid_to,
  is_current=false) and insert a new row.
- fact_grades: ON CONFLICT (grade_id) DO NOTHING — re-runs are safe.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import psycopg
from loguru import logger

# Tracked attributes for SCD2 (must match dim_student column names).
SCD2_TRACKED: tuple[str, ...] = ("city", "study_hours_per_week", "parent_education")


# ---------- helpers ----------------------------------------------------------


def _grade_letter(value: float) -> str:
    if value >= 16:
        return "A"
    if value >= 14:
        return "B"
    if value >= 12:
        return "C"
    if value >= 10:
        return "D"
    return "F"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


# ---------- dim_date ---------------------------------------------------------


@dataclass(frozen=True)
class DimDateRow:
    date_sk: int
    full_date: date
    year: int
    quarter: int
    month: int
    month_name: str
    day_of_month: int
    day_of_week: int
    day_name: str
    week_of_year: int
    is_weekend: bool
    academic_year: str


def _build_dim_date_row(d: date) -> DimDateRow:
    sk = int(d.strftime("%Y%m%d"))
    quarter = (d.month - 1) // 3 + 1
    iso_dow = d.isoweekday()  # 1=Monday..7=Sunday
    is_weekend = iso_dow >= 6
    academic_year = f"{d.year}-{d.year + 1}" if d.month >= 9 else f"{d.year - 1}-{d.year}"
    return DimDateRow(
        date_sk=sk,
        full_date=d,
        year=d.year,
        quarter=quarter,
        month=d.month,
        month_name=d.strftime("%B"),
        day_of_month=d.day,
        day_of_week=iso_dow,
        day_name=d.strftime("%A"),
        week_of_year=int(d.strftime("%W")),
        is_weekend=is_weekend,
        academic_year=academic_year,
    )


def seed_dim_date(dsn: str, start_year: int, end_year: int) -> int:
    rows: list[DimDateRow] = []
    cur_date = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)
    while cur_date <= end_date:
        rows.append(_build_dim_date_row(cur_date))
        cur_date += timedelta(days=1)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO warehouse.dim_date (
                    date_sk, full_date, year, quarter, month, month_name,
                    day_of_month, day_of_week, day_name, week_of_year,
                    is_weekend, academic_year
                ) VALUES (
                    %(date_sk)s, %(full_date)s, %(year)s, %(quarter)s, %(month)s, %(month_name)s,
                    %(day_of_month)s, %(day_of_week)s, %(day_name)s, %(week_of_year)s,
                    %(is_weekend)s, %(academic_year)s
                )
                ON CONFLICT (date_sk) DO NOTHING
                """,
                [r.__dict__ for r in rows],
            )
        conn.commit()
    logger.success("dim_date: {} rows inserted/skipped for {}-{}", len(rows), start_year, end_year)
    return len(rows)


# ---------- dim_school / dim_course (Type 1 UPSERT) --------------------------


def load_dim_schools(dsn: str, csv_path: Path) -> int:
    rows = _read_csv(csv_path)
    if not rows:
        return 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO warehouse.dim_school (school_code, school_name, school_type, city, region)
                VALUES (%(school_code)s, %(school_name)s, %(school_type)s, %(city)s, %(region)s)
                ON CONFLICT (school_code) DO UPDATE SET
                    school_name = EXCLUDED.school_name,
                    school_type = EXCLUDED.school_type,
                    city = EXCLUDED.city,
                    region = EXCLUDED.region,
                    updated_at = now()
                """,
                rows,
            )
        conn.commit()
    logger.success("dim_school: upserted {} rows", len(rows))
    return len(rows)


def load_dim_courses(dsn: str, csv_path: Path) -> int:
    rows = []
    for r in _read_csv(csv_path):
        r["credit_hours"] = int(r["credit_hours"])
        rows.append(r)
    if not rows:
        return 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO warehouse.dim_course (course_code, course_name, subject_area, credit_hours)
                VALUES (%(course_code)s, %(course_name)s, %(subject_area)s, %(credit_hours)s)
                ON CONFLICT (course_code) DO UPDATE SET
                    course_name = EXCLUDED.course_name,
                    subject_area = EXCLUDED.subject_area,
                    credit_hours = EXCLUDED.credit_hours,
                    updated_at = now()
                """,
                rows,
            )
        conn.commit()
    logger.success("dim_course: upserted {} rows", len(rows))
    return len(rows)


# ---------- dim_student (SCD Type 2) -----------------------------------------


@dataclass(frozen=True)
class StudentRow:
    student_code: str
    first_name: str
    last_name: str
    gender: str
    birth_date: date
    city: str
    study_hours_per_week: int
    parent_education: str
    snapshot_date: date


def _student_from_csv(d: dict[str, str]) -> StudentRow:
    return StudentRow(
        student_code=d["student_code"],
        first_name=d["first_name"],
        last_name=d["last_name"],
        gender=d["gender"],
        birth_date=date.fromisoformat(d["birth_date"]),
        city=d["city"],
        study_hours_per_week=int(d["study_hours_per_week"]),
        parent_education=d["parent_education"],
        snapshot_date=date.fromisoformat(d["snapshot_date"]),
    )


def load_dim_student_scd2(dsn: str, csv_path: Path) -> tuple[int, int]:
    """Apply a snapshot CSV using SCD Type 2 logic.

    Returns (rows_inserted, rows_closed).
    Insert rules:
      - If no current row exists for student_code: INSERT a fresh row with valid_from=snapshot_date.
      - If a current row exists and any tracked attribute differs:
          UPDATE the current row to set valid_to=snapshot_date, is_current=false,
          then INSERT a new row valid_from=snapshot_date.
      - Otherwise (current row matches): no-op.
    """
    rows = [_student_from_csv(r) for r in _read_csv(csv_path)]
    inserted = 0
    closed = 0

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for s in rows:
                cur.execute(
                    """
                    SELECT student_sk, city, study_hours_per_week, parent_education
                    FROM warehouse.dim_student
                    WHERE student_code = %s AND is_current
                    """,
                    (s.student_code,),
                )
                current = cur.fetchone()

                if current is None:
                    cur.execute(
                        """
                        INSERT INTO warehouse.dim_student
                            (student_code, first_name, last_name, gender, birth_date,
                             city, study_hours_per_week, parent_education,
                             valid_from, valid_to, is_current)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, DATE '9999-12-31', TRUE)
                        """,
                        (
                            s.student_code,
                            s.first_name,
                            s.last_name,
                            s.gender,
                            s.birth_date,
                            s.city,
                            s.study_hours_per_week,
                            s.parent_education,
                            s.snapshot_date,
                        ),
                    )
                    inserted += 1
                    continue

                _, cur_city, cur_study, cur_pedu = current
                if (
                    cur_city == s.city
                    and cur_study == s.study_hours_per_week
                    and cur_pedu == s.parent_education
                ):
                    # No tracked attribute change; nothing to do.
                    continue

                # Close the current row at snapshot_date and open a new version.
                cur.execute(
                    """
                    UPDATE warehouse.dim_student
                    SET valid_to = %s, is_current = FALSE
                    WHERE student_code = %s AND is_current
                    """,
                    (s.snapshot_date, s.student_code),
                )
                closed += 1
                cur.execute(
                    """
                    INSERT INTO warehouse.dim_student
                        (student_code, first_name, last_name, gender, birth_date,
                         city, study_hours_per_week, parent_education,
                         valid_from, valid_to, is_current)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, DATE '9999-12-31', TRUE)
                    """,
                    (
                        s.student_code,
                        s.first_name,
                        s.last_name,
                        s.gender,
                        s.birth_date,
                        s.city,
                        s.study_hours_per_week,
                        s.parent_education,
                        s.snapshot_date,
                    ),
                )
                inserted += 1
        conn.commit()

    logger.success("dim_student SCD2: {} rows inserted, {} previous rows closed", inserted, closed)
    return inserted, closed


# ---------- fact_grades ------------------------------------------------------


def load_fact_grades(dsn: str, csv_path: Path) -> int:
    """Insert grades, joining each row to the *current* student row (point-in-time
    join would use exam_date BETWEEN valid_from AND valid_to — left as roadmap)."""
    raw = _read_csv(csv_path)
    inserted = 0

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO warehouse.fact_grades (
                    grade_id, student_sk, course_sk, school_sk, exam_date_sk,
                    exam_type, grade_value, grade_letter, is_passing, attempt_number
                )
                SELECT
                    %(grade_id)s,
                    s.student_sk,
                    c.course_sk,
                    sc.school_sk,
                    d.date_sk,
                    %(exam_type)s,
                    %(grade_value)s,
                    %(grade_letter)s,
                    %(is_passing)s,
                    %(attempt_number)s
                FROM warehouse.dim_student s
                JOIN warehouse.dim_course c ON c.course_code = %(course_code)s
                JOIN warehouse.dim_school sc ON sc.school_code = %(school_code)s
                JOIN warehouse.dim_date d ON d.full_date = %(exam_date)s
                WHERE s.student_code = %(student_code)s
                  AND %(exam_date)s::date >= s.valid_from
                  AND %(exam_date)s::date <  s.valid_to
                ON CONFLICT (grade_id) DO NOTHING
                """,
                [
                    {
                        "grade_id": int(r["grade_id"]),
                        "student_code": r["student_code"],
                        "course_code": r["course_code"],
                        "school_code": r["school_code"],
                        "exam_date": r["exam_date"],
                        "exam_type": r["exam_type"],
                        "grade_value": float(r["grade_value"]),
                        "grade_letter": _grade_letter(float(r["grade_value"])),
                        "is_passing": float(r["grade_value"]) >= 10,
                        "attempt_number": int(r["attempt_number"]),
                    }
                    for r in raw
                ],
            )
            inserted = cur.rowcount or 0
        conn.commit()

    logger.success("fact_grades: inserted {} of {} rows", inserted, len(raw))
    return inserted


# ---------- orchestrator -----------------------------------------------------


def load_all(dsn: str, seed_dir: Path) -> dict[str, int]:
    """Load every CSV in seed_dir into the star schema. Returns row counts."""
    counts = {
        "dim_date": seed_dim_date(dsn, 2024, 2026),
        "dim_school": load_dim_schools(dsn, seed_dir / "schools.csv"),
        "dim_course": load_dim_courses(dsn, seed_dir / "courses.csv"),
    }
    s_v1 = seed_dir / "students_v1.csv"
    s_v2 = seed_dir / "students_v2.csv"
    if s_v1.exists():
        ins, _ = load_dim_student_scd2(dsn, s_v1)
        counts["dim_student_v1_inserted"] = ins
    if s_v2.exists():
        ins, closed = load_dim_student_scd2(dsn, s_v2)
        counts["dim_student_v2_inserted"] = ins
        counts["dim_student_closed"] = closed
    counts["fact_grades"] = load_fact_grades(dsn, seed_dir / "grades.csv")
    return counts
