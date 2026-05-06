"""Tests for student_warehouse.config."""

from __future__ import annotations

import pytest

from student_warehouse.config import Settings


def test_dsn_format() -> None:
    s = Settings(  # type: ignore[call-arg]
        _env_file=None,
        postgres_host="db",
        postgres_port=5433,
        postgres_db="w",
        postgres_user="u",
        postgres_password="p",
    )
    assert s.dsn == "postgresql://u:p@db:5433/w"


@pytest.mark.parametrize("port", [0, 65536])
def test_invalid_port_rejected(port: int) -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, postgres_port=port)  # type: ignore[call-arg]


def test_log_level_uppercased() -> None:
    s = Settings(_env_file=None, log_level="debug")  # type: ignore[call-arg]
    assert s.log_level == "DEBUG"
