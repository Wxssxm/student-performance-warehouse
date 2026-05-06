"""Typer CLI for the student warehouse."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from student_warehouse.config import get_settings
from student_warehouse.ddl import apply_ddl
from student_warehouse.loader import (
    load_all,
    load_dim_courses,
    load_dim_schools,
    load_dim_student_scd2,
    load_fact_grades,
    seed_dim_date,
)

app = typer.Typer(
    name="student-warehouse",
    help="Star-schema PostgreSQL warehouse for student-performance data.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command(name="apply-ddl")
def cmd_apply_ddl() -> None:
    """Drop + recreate the warehouse schemas + tables."""
    files = apply_ddl(get_settings().dsn)
    console.print(f"[green]Applied {len(files)} DDL file(s).[/]")


@app.command(name="seed-dim-date")
def cmd_seed_dim_date(
    start: Annotated[int, typer.Option(min=1900, max=2100)] = 2024,
    end: Annotated[int, typer.Option(min=1900, max=2100)] = 2026,
) -> None:
    n = seed_dim_date(get_settings().dsn, start, end)
    console.print(f"[green]dim_date populated for {start}-{end}: {n} rows.[/]")


@app.command()
def load() -> None:
    """Load all CSVs in $SEED_DIR into the star schema."""
    s = get_settings()
    counts = load_all(s.dsn, s.seed_dir)

    table = Table(title="Load summary")
    table.add_column("Step")
    table.add_column("Rows", justify="right")
    for step, n in counts.items():
        table.add_row(step, str(n))
    console.print(table)


@app.command(name="load-students")
def cmd_load_students(csv: Annotated[Path, typer.Argument(exists=True)]) -> None:
    """Apply a single students CSV with SCD2 semantics."""
    inserted, closed = load_dim_student_scd2(get_settings().dsn, csv)
    console.print(f"[green]inserted={inserted} closed={closed}[/]")


@app.command(name="load-schools")
def cmd_load_schools(csv: Annotated[Path, typer.Argument(exists=True)]) -> None:
    n = load_dim_schools(get_settings().dsn, csv)
    console.print(f"[green]upserted {n} schools[/]")


@app.command(name="load-courses")
def cmd_load_courses(csv: Annotated[Path, typer.Argument(exists=True)]) -> None:
    n = load_dim_courses(get_settings().dsn, csv)
    console.print(f"[green]upserted {n} courses[/]")


@app.command(name="load-grades")
def cmd_load_grades(csv: Annotated[Path, typer.Argument(exists=True)]) -> None:
    n = load_fact_grades(get_settings().dsn, csv)
    console.print(f"[green]inserted {n} grades[/]")


@app.command(name="load-all")
def cmd_load_all() -> None:
    """One-shot bootstrap: apply DDL, seed dim_date, then load CSVs."""
    s = get_settings()
    apply_ddl(s.dsn)
    seed_dim_date(s.dsn, 2024, 2026)
    counts = load_all(s.dsn, s.seed_dir)
    console.print(counts)


if __name__ == "__main__":
    app()
