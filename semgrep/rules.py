# ai-generated: 100% - Claude Code (Opus 5.5) wrote this test file for semgrep/rules.yml (CI-SPEC.md P-31); the lecturer reviews it
import time
from datetime import UTC, datetime

from svcdesk import clock


def update(conn, assignments, values, ticket_id):
    # ruleid: svcdesk-sql-text-built-at-run-time
    conn.execute(f"UPDATE tickets SET {assignments} WHERE id = ?", [*values, ticket_id])


def get(conn, ticket_id):
    # ok: svcdesk-sql-text-built-at-run-time
    return conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()


def stamp():
    # ruleid: svcdesk-wall-clock-read
    created = datetime.now(UTC)
    # ruleid: svcdesk-wall-clock-read
    started = time.time()
    # ok: svcdesk-wall-clock-read
    due = clock.now()
    # ok: svcdesk-wall-clock-read
    parsed = datetime.fromisoformat("2026-11-14T08:00:00+00:00")
    return created, started, due, parsed
