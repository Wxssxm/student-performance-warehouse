"""Apply / drop DDL by reading the .sql files in sql/ddl/ in order."""

from __future__ import annotations

from pathlib import Path

import psycopg
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DDL_DIR = PROJECT_ROOT / "sql" / "ddl"


def apply_ddl(dsn: str, ddl_dir: Path = DDL_DIR) -> list[Path]:
    """Apply every *.sql file in ddl_dir alphabetically. Returns the list of applied files."""
    files = sorted(ddl_dir.glob("*.sql"))
    if not files:
        raise FileNotFoundError(f"No .sql files found in {ddl_dir}")

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for f in files:
                logger.info("Applying {}", f.name)
                cur.execute(f.read_text())
        conn.commit()

    logger.success("Applied {} DDL file(s)", len(files))
    return files
