"""Pure-function tests — no DB required."""

from __future__ import annotations

from datetime import date

import pytest

from student_warehouse.loader import _build_dim_date_row, _grade_letter


@pytest.mark.parametrize(
    "value,expected",
    [
        (20, "A"),
        (16, "A"),
        (15.9, "B"),
        (14.0, "B"),
        (13.5, "C"),
        (12.0, "C"),
        (11.0, "D"),
        (10.0, "D"),
        (9.9, "F"),
        (0.0, "F"),
    ],
)
def test_grade_letter(value: float, expected: str) -> None:
    assert _grade_letter(value) == expected


def test_dim_date_row_september_is_new_academic_year() -> None:
    row = _build_dim_date_row(date(2024, 9, 1))
    assert row.date_sk == 20240901
    assert row.year == 2024
    assert row.month == 9
    assert row.quarter == 3
    assert row.academic_year == "2024-2025"


def test_dim_date_row_january_is_carryover_academic_year() -> None:
    row = _build_dim_date_row(date(2025, 1, 15))
    assert row.academic_year == "2024-2025"


def test_dim_date_row_weekend_flag_saturday() -> None:
    row = _build_dim_date_row(date(2025, 3, 8))  # Saturday
    assert row.is_weekend is True
    assert row.day_of_week == 6


def test_dim_date_row_weekday_flag_wednesday() -> None:
    row = _build_dim_date_row(date(2025, 3, 5))  # Wednesday
    assert row.is_weekend is False
    assert row.day_of_week == 3
