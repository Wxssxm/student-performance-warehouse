"""Provision Metabase: log in as admin, create the Postgres datasource.

Use this AFTER running `docker compose up` — Metabase needs to have completed
its first-run setup (visit http://localhost:3000 once and create the admin
account, then run this script). The dashboard itself can be authored via the
UI; the heavy lifting (schema discovery, queries) is automated by Metabase
once the datasource exists.

Re-running is safe: existing datasources with the same name are skipped.
"""

from __future__ import annotations

import os
import sys

import httpx

METABASE_URL = os.environ.get("METABASE_URL", "http://localhost:3000")
ADMIN_EMAIL = os.environ.get("METABASE_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("METABASE_ADMIN_PASSWORD", "admin_dev_only")

DB_NAME = "Student Warehouse"
DB_PAYLOAD = {
    "engine": "postgres",
    "name": DB_NAME,
    "details": {
        "host": "postgres",  # docker-compose service name
        "port": 5432,
        "dbname": os.environ.get("POSTGRES_DB", "student_warehouse"),
        "user": os.environ.get("POSTGRES_USER", "warehouse"),
        "password": os.environ.get("POSTGRES_PASSWORD", "warehouse_dev_only"),
        "ssl": False,
    },
}


def _login(client: httpx.Client) -> str:
    r = client.post(
        f"{METABASE_URL}/api/session",
        json={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    r.raise_for_status()
    return r.json()["id"]


def _get_databases(client: httpx.Client, token: str) -> list[dict]:
    r = client.get(f"{METABASE_URL}/api/database", headers={"X-Metabase-Session": token})
    r.raise_for_status()
    payload = r.json()
    return payload.get("data", payload) if isinstance(payload, dict) else payload


def _create_database(client: httpx.Client, token: str) -> dict:
    r = client.post(
        f"{METABASE_URL}/api/database",
        headers={"X-Metabase-Session": token},
        json=DB_PAYLOAD,
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    with httpx.Client(timeout=15) as client:
        try:
            token = _login(client)
        except httpx.HTTPStatusError as exc:
            print(
                f"[error] Could not log into Metabase at {METABASE_URL}. "
                f"Did you complete the admin first-run flow? ({exc})",
                file=sys.stderr,
            )
            return 1

        existing = _get_databases(client, token)
        if any(d.get("name") == DB_NAME for d in existing):
            print(f"[ok] Datasource '{DB_NAME}' already exists; nothing to do.")
            return 0

        created = _create_database(client, token)
        print(f"[ok] Created datasource '{DB_NAME}' (id={created.get('id')}).")
        print("    Open http://localhost:3000 to start querying.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
