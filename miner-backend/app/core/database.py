from __future__ import annotations

import sqlite3
import os
import logging
import re
from datetime import datetime
from pathlib import Path

from app.core.config import settings

log = logging.getLogger(__name__)


def sqlite_path_from_url(value: str) -> Path:
    if value.startswith("jdbc:sqlite:"):
        value = value.removeprefix("jdbc:sqlite:")
    if value.startswith("sqlite:///"):
        value = value.removeprefix("sqlite:///")

    windows_path = re.match(r"^([A-Za-z]):[\\/](.*)$", value)
    if windows_path and os.name != "nt":
        drive, path = windows_path.groups()
        return Path.home() / ".miner-backend" / drive.lower() / Path(
            path.replace("\\", "/")
        )

    return Path(value)


DATABASE_PATH = sqlite_path_from_url(settings.database_url)
SCHEMA_PATH = Path(__file__).with_name("database.sql")


MINING_RUN_COLUMN_MIGRATIONS = {
    "progress_stage": "ALTER TABLE mining_runs ADD COLUMN progress_stage TEXT",
    "total_candidates": (
        "ALTER TABLE mining_runs ADD COLUMN total_candidates INTEGER NOT NULL DEFAULT 0"
    ),
    "processed_repositories": (
        "ALTER TABLE mining_runs ADD COLUMN processed_repositories INTEGER NOT NULL DEFAULT 0"
    ),
    "accepted_repositories": (
        "ALTER TABLE mining_runs ADD COLUMN accepted_repositories INTEGER NOT NULL DEFAULT 0"
    ),
    "eliminated_repositories": (
        "ALTER TABLE mining_runs ADD COLUMN eliminated_repositories INTEGER NOT NULL DEFAULT 0"
    ),
    "analyze": "ALTER TABLE mining_runs ADD COLUMN analyze INTEGER NOT NULL DEFAULT 0",
    "allow_jdk_upgrade": (
        "ALTER TABLE mining_runs ADD COLUMN allow_jdk_upgrade INTEGER NOT NULL DEFAULT 0"
    ),
    "provider": "ALTER TABLE mining_runs ADD COLUMN provider TEXT NOT NULL DEFAULT 'github'",
    "page_cursor": (
        "ALTER TABLE mining_runs ADD COLUMN page_cursor INTEGER NOT NULL DEFAULT 1"
    ),
    "per_page": "ALTER TABLE mining_runs ADD COLUMN per_page INTEGER NOT NULL DEFAULT 100",
    "last_processed_index": (
        "ALTER TABLE mining_runs ADD COLUMN last_processed_index INTEGER NOT NULL DEFAULT 0"
    ),
    "acceptance_rate": (
        "ALTER TABLE mining_runs ADD COLUMN acceptance_rate REAL NOT NULL DEFAULT 0.25"
    ),
    "batch_size": "ALTER TABLE mining_runs ADD COLUMN batch_size INTEGER",
    "exhausted": "ALTER TABLE mining_runs ADD COLUMN exhausted INTEGER NOT NULL DEFAULT 0",
}


MINING_RUN_CANDIDATE_COLUMN_MIGRATIONS = {
    "matched_filter": "ALTER TABLE mining_run_candidates ADD COLUMN matched_filter TEXT",
    "matched_file": "ALTER TABLE mining_run_candidates ADD COLUMN matched_file TEXT",
    "metadata_json": "ALTER TABLE mining_run_candidates ADD COLUMN metadata_json TEXT",
}


SEARCH_FILTER_COLUMN_MIGRATIONS = {
    "content_rules_json": "ALTER TABLE search_filters ADD COLUMN content_rules_json TEXT",
}


ANALYSIS_RESULT_COLUMN_MIGRATIONS = {
    "test_frameworks": "ALTER TABLE analysis_results ADD COLUMN test_frameworks TEXT",
    "mock_libraries": "ALTER TABLE analysis_results ADD COLUMN mock_libraries TEXT",
    "assertion_libraries": "ALTER TABLE analysis_results ADD COLUMN assertion_libraries TEXT",
    "integration_test_tools": "ALTER TABLE analysis_results ADD COLUMN integration_test_tools TEXT",
    "compile_duration_seconds": "ALTER TABLE analysis_results ADD COLUMN compile_duration_seconds REAL",
    "test_duration_seconds": "ALTER TABLE analysis_results ADD COLUMN test_duration_seconds REAL",
}


ANALYSIS_CACHE_COLUMN_MIGRATIONS = {
    "allow_jdk_upgrade": (
        "ALTER TABLE analysis_cache ADD COLUMN allow_jdk_upgrade INTEGER NOT NULL DEFAULT 0"
    ),
    "test_frameworks": "ALTER TABLE analysis_cache ADD COLUMN test_frameworks TEXT",
    "mock_libraries": "ALTER TABLE analysis_cache ADD COLUMN mock_libraries TEXT",
    "assertion_libraries": "ALTER TABLE analysis_cache ADD COLUMN assertion_libraries TEXT",
    "integration_test_tools": "ALTER TABLE analysis_cache ADD COLUMN integration_test_tools TEXT",
    "compile_duration_seconds": "ALTER TABLE analysis_cache ADD COLUMN compile_duration_seconds REAL",
    "test_duration_seconds": "ALTER TABLE analysis_cache ADD COLUMN test_duration_seconds REAL",
}


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError as exc:
        log.warning(
            "SQLite WAL indisponivel para %s; usando journal_mode=DELETE. Erro original: %s",
            DATABASE_PATH,
            exc,
        )
        conn.execute("PRAGMA journal_mode = DELETE")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def is_database_corruption_error(exc: sqlite3.DatabaseError) -> bool:
    message = str(exc).lower()
    return (
        "database disk image is malformed" in message
        or "file is not a database" in message
    )


def backup_corrupt_database() -> list[Path]:
    if not DATABASE_PATH.exists():
        return []

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backed_up: list[Path] = []
    sidecar_paths = (
        DATABASE_PATH,
        DATABASE_PATH.with_name(f"{DATABASE_PATH.name}-wal"),
        DATABASE_PATH.with_name(f"{DATABASE_PATH.name}-shm"),
    )
    for path in sidecar_paths:
        if not path.exists():
            continue

        backup_path = path.with_name(f"{path.name}.corrupt-{timestamp}")
        suffix = 1
        while backup_path.exists():
            backup_path = path.with_name(f"{path.name}.corrupt-{timestamp}-{suffix}")
            suffix += 1

        path.rename(backup_path)
        backed_up.append(backup_path)

    return backed_up


def init_database_once() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection() as conn:
        conn.executescript(schema)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(mining_runs)").fetchall()
        }
        for column, statement in MINING_RUN_COLUMN_MIGRATIONS.items():
            if column not in columns:
                conn.execute(statement)

        search_filter_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(search_filters)").fetchall()
        }
        for column, statement in SEARCH_FILTER_COLUMN_MIGRATIONS.items():
            if column not in search_filter_columns:
                conn.execute(statement)

        analysis_result_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(analysis_results)").fetchall()
        }
        for column, statement in ANALYSIS_RESULT_COLUMN_MIGRATIONS.items():
            if column not in analysis_result_columns:
                conn.execute(statement)

        analysis_cache_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(analysis_cache)").fetchall()
        }
        for column, statement in ANALYSIS_CACHE_COLUMN_MIGRATIONS.items():
            if column not in analysis_cache_columns:
                conn.execute(statement)

        candidate_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(mining_run_candidates)").fetchall()
        }
        for column, statement in MINING_RUN_CANDIDATE_COLUMN_MIGRATIONS.items():
            if column not in candidate_columns:
                conn.execute(statement)


def init_database() -> None:
    try:
        init_database_once()
    except sqlite3.DatabaseError as exc:
        if not is_database_corruption_error(exc):
            raise

        backed_up = backup_corrupt_database()
        log.error(
            "Banco SQLite corrompido em %s; backups criados em %s. Recriando banco vazio.",
            DATABASE_PATH,
            ", ".join(str(path) for path in backed_up) or "nenhum arquivo",
        )
        init_database_once()
