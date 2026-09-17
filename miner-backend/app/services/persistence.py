from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.core.database import get_connection, init_database
from app.schemas.repository_models import MinedRepo, mined_repo_to_dict
from app.schemas.repository_requests import GitHubSearchFilterRequest, SearchRepositoriesRequest
from app.services.filters import GitHubSearchFilter
from app.services.persistence_policy import should_persist_repository


def bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def json_value(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def metadata(repo: dict[str, Any]) -> dict[str, Any]:
    value = repo.get("metadata")
    return value if isinstance(value, dict) else {}


def repo_name(repo: dict[str, Any]) -> str:
    return str(repo.get("name") or repo.get("repo_name") or "")


def repo_url(repo: dict[str, Any]) -> str:
    return str(repo.get("repository_url") or repo.get("repo_url") or "")


def create_mining_run(payload: SearchRepositoriesRequest, status: str = "running") -> int:
    init_database()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO mining_runs (
                status,
                progress_stage,
                statistics_scope,
                analyze,
                include_statistics,
                require_buildable,
                require_tests_passed,
                allow_jdk_upgrade,
                persist_eliminated_repositories,
                max_repos,
                max_workers,
                analyzer_workers,
                delay_seconds,
                provider,
                page_cursor,
                per_page,
                last_processed_index,
                acceptance_rate,
                exhausted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                status,
                status,
                payload.statistics_scope,
                bool_int(payload.analyze),
                bool_int(payload.include_statistics),
                bool_int(payload.require_buildable),
                bool_int(payload.require_tests_passed),
                bool_int(payload.allow_jdk_upgrade),
                bool_int(payload.persist_eliminated_repositories),
                payload.max_repos,
                payload.max_workers,
                payload.analyzer_workers,
                payload.delay,
                "github",
                1,
                100,
                0,
                0.25,
                0,
            ),
        )
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("SQLite não retornou o ID da execução")

        return lastrowid


def update_mining_run_progress(
    run_id: int,
    *,
    status: str | None = None,
    progress_stage: str | None = None,
    total_candidates: int | None = None,
    processed_repositories: int | None = None,
    accepted_repositories: int | None = None,
    eliminated_repositories: int | None = None,
) -> None:
    updates: list[str] = []
    values: list[Any] = []

    fields = {
        "status": status,
        "progress_stage": progress_stage,
        "total_candidates": total_candidates,
        "processed_repositories": processed_repositories,
        "accepted_repositories": accepted_repositories,
        "eliminated_repositories": eliminated_repositories,
    }
    for field_name, value in fields.items():
        if value is not None:
            updates.append(f"{field_name} = ?")
            values.append(value)

    if not updates:
        return

    values.append(run_id)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE mining_runs SET {', '.join(updates)} WHERE id = ?",
            values,
        )


def update_mining_run_checkpoint(
    run_id: int,
    *,
    page_cursor: int | None = None,
    per_page: int | None = None,
    last_processed_index: int | None = None,
    acceptance_rate: float | None = None,
    batch_size: int | None = None,
    exhausted: bool | None = None,
) -> None:
    updates: list[str] = []
    values: list[Any] = []

    fields: dict[str, Any] = {
        "page_cursor": page_cursor,
        "per_page": per_page,
        "last_processed_index": last_processed_index,
        "acceptance_rate": acceptance_rate,
        "batch_size": batch_size,
        "exhausted": None if exhausted is None else bool_int(exhausted),
    }
    for field_name, value in fields.items():
        if value is not None:
            updates.append(f"{field_name} = ?")
            values.append(value)

    if not updates:
        return

    values.append(run_id)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE mining_runs SET {', '.join(updates)} WHERE id = ?",
            values,
        )


def finish_mining_run(run_id: int, status: str = "completed", error_message: str | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE mining_runs
            SET status = ?,
                progress_stage = ?,
                finished_at = CURRENT_TIMESTAMP,
                error_message = ?
            WHERE id = ?
            """,
            (status, status, error_message, run_id),
        )


def restart_mining_run(run_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE mining_runs
            SET status = 'queued',
                progress_stage = 'queued',
                finished_at = NULL,
                error_message = NULL
            WHERE id = ?
            """,
            (run_id,),
        )


def cancel_mining_run(run_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE mining_runs
            SET status = 'cancelled',
                progress_stage = 'cancelled',
                finished_at = CURRENT_TIMESTAMP,
                error_message = NULL
            WHERE id = ?
              AND status IN ('queued', 'running', 'failed', 'cancelled')
            """,
            (run_id,),
        )


def is_mining_run_cancelled(run_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT status FROM mining_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    return row is not None and row["status"] == "cancelled"


def get_mining_run(run_id: int) -> dict[str, Any] | None:
     
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                status,
                progress_stage,
                total_candidates,
                processed_repositories,
                accepted_repositories,
                eliminated_repositories,
                statistics_scope,
                analyze,
                include_statistics,
                require_buildable,
                require_tests_passed,
                allow_jdk_upgrade,
                persist_eliminated_repositories,
                max_repos,
                max_workers,
                analyzer_workers,
                delay_seconds,
                provider,
                page_cursor,
                per_page,
                last_processed_index,
                acceptance_rate,
                batch_size,
                exhausted,
                started_at,
                finished_at,
                error_message
            FROM mining_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def upsert_mining_run_candidate(
    run_id: int,
    *,
    page_number: int,
    page_index: int,
    repo_full_name: str,
    repo_url: str,
    commit_sha: str | None = None,
    matched_filter: str | None = None,
    matched_file: str | None = None,
    status: str = "pending",
    rejection_stage: str | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    upsert_mining_run_candidates_batch(
        run_id,
        [
            {
                "page_number": page_number,
                "page_index": page_index,
                "repo_full_name": repo_full_name,
                "repo_url": repo_url,
                "commit_sha": commit_sha,
                "matched_filter": matched_filter,
                "matched_file": matched_file,
                "status": status,
                "rejection_stage": rejection_stage,
                "error_message": error_message,
                "metadata": metadata,
            }
        ],
    )


def upsert_mining_run_candidates_batch(
    run_id: int,
    candidates: list[dict[str, Any]],
) -> None:
    if not candidates:
        return

    rows = [
        (
            run_id,
            candidate["page_number"],
            candidate["page_index"],
            candidate["repo_full_name"],
            candidate["repo_url"],
            candidate.get("commit_sha"),
            candidate.get("matched_filter"),
            candidate.get("matched_file"),
            candidate.get("status", "pending"),
            candidate.get("rejection_stage"),
            candidate.get("error_message"),
            json_text(candidate.get("metadata") or {}),
        )
        for candidate in candidates
    ]

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO mining_run_candidates (
                mining_run_id,
                page_number,
                page_index,
                repo_full_name,
                repo_url,
                commit_sha,
                matched_filter,
                matched_file,
                status,
                rejection_stage,
                error_message,
                metadata_json,
                processed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(mining_run_id, repo_full_name, commit_sha)
            DO UPDATE SET
                page_number = excluded.page_number,
                page_index = excluded.page_index,
                repo_url = excluded.repo_url,
                matched_filter = excluded.matched_filter,
                matched_file = excluded.matched_file,
                status = excluded.status,
                rejection_stage = excluded.rejection_stage,
                error_message = excluded.error_message,
                metadata_json = excluded.metadata_json,
                processed_at = CURRENT_TIMESTAMP
            """,
            rows,
        )


def save_search_filters(
    run_id: int,
    raw_filters: list[GitHubSearchFilterRequest],
    built_filters: list[GitHubSearchFilter],
) -> dict[str, int]:
    filter_ids: dict[str, int] = {}

    with get_connection() as conn:
        existing_rows = conn.execute(
            "SELECT id, name FROM search_filters WHERE mining_run_id = ?",
            (run_id,),
        ).fetchall()
        filter_ids.update({str(row["name"]): int(row["id"]) for row in existing_rows})

        for raw_filter, built_filter in zip(raw_filters, built_filters):
            if raw_filter.name in filter_ids:
                continue

            cursor = conn.execute(
                """
                INSERT INTO search_filters (
                    mining_run_id,
                    name,
                    search_type,
                    raw_query,
                    built_query,
                    language,
                    stars,
                    forks,
                    size,
                    created_range,
                    pushed_range,
                    topic,
                    license_key,
                    visibility,
                    user_filter,
                    org_filter,
                    repo_filter,
                    followers,
                    topics,
                    fork_filter,
                    archived,
                    mirror,
                    template,
                    good_first_issues,
                    help_wanted_issues,
                    filename,
                    extension,
                    path_filter,
                    content_rules_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    raw_filter.name,
                    raw_filter.search_type,
                    raw_filter.query,
                    built_filter.query,
                    raw_filter.language,
                    raw_filter.stars,
                    raw_filter.forks,
                    raw_filter.size,
                    raw_filter.created,
                    raw_filter.pushed,
                    raw_filter.topic,
                    raw_filter.license,
                    raw_filter.visibility,
                    raw_filter.user,
                    raw_filter.org,
                    raw_filter.repo,
                    raw_filter.followers,
                    raw_filter.topics,
                    raw_filter.fork,
                    None if raw_filter.archived is None else bool_int(raw_filter.archived),
                    None if raw_filter.mirror is None else bool_int(raw_filter.mirror),
                    None if raw_filter.template is None else bool_int(raw_filter.template),
                    raw_filter.good_first_issues,
                    raw_filter.help_wanted_issues,
                    raw_filter.filename,
                    raw_filter.extension,
                    raw_filter.path,
                    json_text([rule.model_dump() for rule in raw_filter.content_rules]),
                ),
            )
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("Não foi possível obter o ID do filtro")

            filter_ids[raw_filter.name] = lastrowid

    return filter_ids


def get_search_filters_for_run(run_id: int) -> list[GitHubSearchFilterRequest]:
     
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                name,
                search_type,
                raw_query,
                language,
                stars,
                forks,
                size,
                created_range,
                pushed_range,
                topic,
                license_key,
                visibility,
                user_filter,
                org_filter,
                repo_filter,
                followers,
                topics,
                fork_filter,
                archived,
                mirror,
                template,
                good_first_issues,
                help_wanted_issues,
                filename,
                extension,
                path_filter,
                content_rules_json
            FROM search_filters
            WHERE mining_run_id = ?
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()

    filters: list[GitHubSearchFilterRequest] = []
    seen_names: set[str] = set()
    for row in rows:
        name = str(row["name"])
        if name in seen_names:
            continue
        seen_names.add(name)

        filters.append(
            GitHubSearchFilterRequest(
                name=name,
                search_type=row["search_type"],
                query=row["raw_query"],
                language=row["language"],
                stars=row["stars"],
                forks=row["forks"],
                size=row["size"],
                created=row["created_range"],
                pushed=row["pushed_range"],
                topic=row["topic"],
                license=row["license_key"],
                visibility=row["visibility"],
                user=row["user_filter"],
                org=row["org_filter"],
                repo=row["repo_filter"],
                followers=row["followers"],
                topics=row["topics"],
                fork=row["fork_filter"],
                archived=None if row["archived"] is None else bool(row["archived"]),
                mirror=None if row["mirror"] is None else bool(row["mirror"]),
                template=None if row["template"] is None else bool(row["template"]),
                good_first_issues=row["good_first_issues"],
                help_wanted_issues=row["help_wanted_issues"],
                filename=row["filename"],
                extension=row["extension"],
                path=row["path_filter"],
                content_rules=json_value(row["content_rules_json"], []),
            )
        )

    return filters


def get_processed_candidate_keys(run_id: int) -> set[str]:
     
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT repo_full_name, matched_file
            FROM mining_run_candidates
            WHERE mining_run_id = ?
            """,
            (run_id,),
        ).fetchall()

    keys: set[str] = set()
    for row in rows:
        matched_file = row["matched_file"]
        full_name = str(row["repo_full_name"])
        keys.add(f"{full_name}:{matched_file}" if matched_file else full_name)
    return keys


def _upsert_repository(conn: sqlite3.Connection, repo: dict[str, Any]) -> int:
    meta = metadata(repo)
    full_name = repo_name(repo)
    html_url = repo_url(repo)

    conn.execute(
            """
            INSERT INTO repositories (
                full_name,
                html_url,
                description,
                language,
                stars,
                forks,
                open_issues,
                topics,
                github_created_at,
                github_updated_at,
                github_pushed_at,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(full_name)
            DO UPDATE SET
                html_url = excluded.html_url,
                description = excluded.description,
                language = excluded.language,
                stars = excluded.stars,
                forks = excluded.forks,
                open_issues = excluded.open_issues,
                topics = excluded.topics,
                github_created_at = excluded.github_created_at,
                github_updated_at = excluded.github_updated_at,
                github_pushed_at = excluded.github_pushed_at,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (
                full_name,
                html_url,
                meta.get("description"),
                meta.get("language"),
                meta.get("stars"),
                meta.get("forks"),
                meta.get("open_issues"),
                json_text(meta.get("topics", [])),
                meta.get("created_at"),
                meta.get("updated_at"),
                meta.get("pushed_at"),
            ),
        )
    row = conn.execute(
        "SELECT id FROM repositories WHERE full_name = ?",
        (full_name,),
    ).fetchone()

    if row is None:
        raise RuntimeError(f"SQLite não retornou o repositório: {full_name}")

    return int(row["id"])


def upsert_repository(repo: dict[str, Any]) -> int:
    with get_connection() as conn:
        return _upsert_repository(conn, repo)


def _save_run_repository(
    conn: sqlite3.Connection,
    run_id: int,
    repository_id: int,
    repo: dict[str, Any],
    filter_ids: dict[str, int],
) -> int:
    meta = metadata(repo)
    matched_filter = str(repo.get("matched_filter") or "")

    conn.execute(
            """
            INSERT INTO run_repositories (
                mining_run_id,
                repository_id,
                search_filter_id,
                matched_filter,
                matched_file,
                commit_sha,
                java_version,
                metadata,
                accepted,
                eliminated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mining_run_id, repository_id, matched_file)
            DO UPDATE SET
                search_filter_id = excluded.search_filter_id,
                matched_filter = excluded.matched_filter,
                commit_sha = excluded.commit_sha,
                java_version = excluded.java_version,
                metadata = excluded.metadata,
                accepted = excluded.accepted,
                eliminated = excluded.eliminated
            """,
            (
                run_id,
                repository_id,
                filter_ids.get(matched_filter),
                matched_filter or None,
                meta.get("matched_file"),
                repo.get("commit_sha"),
                repo.get("java_version") or meta.get("java_version"),
                json_text(meta),
                None if "eliminated" not in repo else bool_int(not repo.get("eliminated")),
                None if "eliminated" not in repo else bool_int(repo.get("eliminated")),
            ),
        )
    row = conn.execute(
        """
        SELECT id
        FROM run_repositories
        WHERE mining_run_id = ?
          AND repository_id = ?
          AND COALESCE(matched_file, '') = COALESCE(?, '')
        """,
        (run_id, repository_id, meta.get("matched_file")),
    ).fetchone()

    if row is None:
        raise RuntimeError("SQLite não retornou o repositório da execução")

    return int(row["id"])


def save_run_repository(
    run_id: int,
    repository_id: int,
    repo: dict[str, Any],
    filter_ids: dict[str, int],
) -> int:
    with get_connection() as conn:
        return _save_run_repository(conn, run_id, repository_id, repo, filter_ids)


def _save_analysis_result(
    conn: sqlite3.Connection,
    run_repository_id: int,
    repo: dict[str, Any],
) -> None:
    conn.execute(
            """
            INSERT INTO analysis_results (
                run_repository_id,
                declared_java_version,
                effective_java_version,
                build_tool,
                test_framework,
                compiled,
                has_tests,
                tests_passed,
                eliminated,
                error_stage,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_repository_id)
            DO UPDATE SET
                declared_java_version = excluded.declared_java_version,
                effective_java_version = excluded.effective_java_version,
                build_tool = excluded.build_tool,
                test_framework = excluded.test_framework,
                compiled = excluded.compiled,
                has_tests = excluded.has_tests,
                tests_passed = excluded.tests_passed,
                eliminated = excluded.eliminated,
                error_stage = excluded.error_stage,
                error_message = excluded.error_message,
                analyzed_at = CURRENT_TIMESTAMP
            """,
            (
                run_repository_id,
                repo.get("java_version"),
                repo.get("effective_java_version"),
                repo.get("build"),
                repo.get("test_framework"),
                bool_int(repo.get("compiled")),
                bool_int(repo.get("has_tests")),
                bool_int(repo.get("tests_passed")),
                bool_int(repo.get("eliminated")),
                repo.get("error_stage"),
                repo.get("error_message"),
            ),
    )


def save_analysis_result(run_repository_id: int, repo: dict[str, Any]) -> None:
    with get_connection() as conn:
        _save_analysis_result(conn, run_repository_id, repo)


def _save_analysis_cache(
    conn: sqlite3.Connection,
    repository_id: int,
    repo: dict[str, Any],
    run_test_suite: bool,
    allow_jdk_upgrade: bool,
) -> None:
    commit_sha = str(repo.get("commit_sha") or "").strip()
    if not commit_sha:
        return

    conn.execute(
            """
            INSERT INTO analysis_cache (
                repository_id,
                commit_sha,
                run_test_suite,
                allow_jdk_upgrade,
                declared_java_version,
                effective_java_version,
                build_tool,
                test_framework,
                compiled,
                has_tests,
                tests_passed,
                eliminated,
                error_stage,
                error_summary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repository_id, commit_sha, run_test_suite)
            DO UPDATE SET
                allow_jdk_upgrade = excluded.allow_jdk_upgrade,
                declared_java_version = excluded.declared_java_version,
                effective_java_version = excluded.effective_java_version,
                build_tool = excluded.build_tool,
                test_framework = excluded.test_framework,
                compiled = excluded.compiled,
                has_tests = excluded.has_tests,
                tests_passed = excluded.tests_passed,
                eliminated = excluded.eliminated,
                error_stage = excluded.error_stage,
                error_summary = excluded.error_summary,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                repository_id,
                commit_sha,
                bool_int(run_test_suite),
                bool_int(allow_jdk_upgrade),
                repo.get("java_version"),
                repo.get("effective_java_version"),
                repo.get("build"),
                repo.get("test_framework"),
                bool_int(repo.get("compiled")),
                bool_int(repo.get("has_tests")),
                bool_int(repo.get("tests_passed")),
                bool_int(repo.get("eliminated")),
                repo.get("error_stage"),
                str(repo.get("error_message") or "")[:1000] or None,
            ),
    )


def save_analysis_cache(
    repository_id: int,
    repo: dict[str, Any],
    run_test_suite: bool,
    allow_jdk_upgrade: bool = False,
) -> None:
    with get_connection() as conn:
        _save_analysis_cache(conn, repository_id, repo, run_test_suite, allow_jdk_upgrade)


def save_statistics(run_id: int, statistics: dict[str, Any] | None) -> None:
    if statistics is None:
        return

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO run_statistics (mining_run_id, scope, statistics)
            VALUES (?, ?, ?)
            """,
            (
                run_id,
                statistics.get("scope", "accepted"),
                json_text(statistics),
            ),
        )


def get_run_repositories(run_id: int) -> list[dict[str, Any]]:
     
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                r.full_name,
                r.html_url,
                rr.matched_filter,
                rr.matched_file,
                rr.commit_sha,
                rr.java_version AS mined_java_version,
                rr.metadata,
                rr.accepted,
                rr.eliminated AS run_eliminated,
                ar.declared_java_version,
                ar.effective_java_version,
                ar.build_tool,
                ar.test_framework,
                ar.compiled,
                ar.has_tests,
                ar.tests_passed,
                ar.eliminated AS analysis_eliminated,
                ar.error_stage,
                ar.error_message,
                ar.analyzed_at
            FROM run_repositories rr
            JOIN repositories r ON r.id = rr.repository_id
            LEFT JOIN analysis_results ar ON ar.run_repository_id = rr.id
            WHERE rr.mining_run_id = ?
            ORDER BY rr.id
            """,
            (run_id,),
        ).fetchall()

    repositories: list[dict[str, Any]] = []
    for row in rows:
        meta = json_value(row["metadata"], {})
        if not isinstance(meta, dict):
            meta = {}
        repo = {
            "repo_name": row["full_name"],
            "repo_url": row["html_url"],
            "matched_filter": row["matched_filter"],
            "metadata": meta,
        }
        if row["matched_file"] is not None:
            repo["metadata"]["matched_file"] = row["matched_file"]
        if row["commit_sha"] is not None:
            repo["commit_sha"] = row["commit_sha"]
        if row["mined_java_version"] is not None:
            repo["java_version"] = row["mined_java_version"]

        if row["declared_java_version"] is not None:
            repo.update(
                {
                    "java_version": row["declared_java_version"],
                    "effective_java_version": row["effective_java_version"],
                    "build": row["build_tool"],
                    "test_framework": row["test_framework"],
                    "compiled": bool(row["compiled"]),
                    "has_tests": bool(row["has_tests"]),
                    "tests_passed": bool(row["tests_passed"]),
                    "eliminated": bool(row["analysis_eliminated"]),
                    "error_stage": row["error_stage"],
                    "error_message": row["error_message"],
                    "analyzed_at": row["analyzed_at"],
                }
            )
        elif row["run_eliminated"] is not None:
            repo["eliminated"] = bool(row["run_eliminated"])
            repo["accepted"] = bool(row["accepted"])

        repositories.append(repo)

    return repositories


def get_run_statistics(run_id: int) -> dict[str, Any] | None:
     
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT statistics
            FROM run_statistics
            WHERE mining_run_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()

    if row is None:
        return None
    value = json_value(row["statistics"], None)
    return value if isinstance(value, dict) else None


def get_analysis_cache(
    full_name: str,
    commit_sha: str,
    run_test_suite: bool,
    allow_jdk_upgrade: bool = False,
) -> dict[str, Any] | None:
    if not full_name or not commit_sha:
        return None

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                ac.commit_sha,
                ac.allow_jdk_upgrade,
                ac.declared_java_version,
                ac.effective_java_version,
                ac.build_tool,
                ac.test_framework,
                ac.compiled,
                ac.has_tests,
                ac.tests_passed,
                ac.eliminated,
                ac.error_stage,
                ac.error_summary
            FROM analysis_cache ac
            JOIN repositories r ON r.id = ac.repository_id
            WHERE r.full_name = ?
              AND ac.commit_sha = ?
              AND ac.run_test_suite = ?
              AND ac.allow_jdk_upgrade = ?
            LIMIT 1
            """,
            (full_name, commit_sha, bool_int(run_test_suite), bool_int(allow_jdk_upgrade)),
        ).fetchone()

    if row is None:
        return None

    return {
        "commit_sha": row["commit_sha"],
        "allow_jdk_upgrade": bool(row["allow_jdk_upgrade"]),
        "java_version": row["declared_java_version"],
        "effective_java_version": row["effective_java_version"],
        "build": row["build_tool"],
        "test_framework": row["test_framework"],
        "compiled": bool(row["compiled"]),
        "has_tests": bool(row["has_tests"]),
        "tests_passed": bool(row["tests_passed"]),
        "eliminated": bool(row["eliminated"]),
        "error_stage": row["error_stage"],
        "error_message": row["error_summary"],
        "cache_hit": True,
    }


def get_latest_analysis_cache(
    full_name: str,
    run_test_suite: bool,
    allow_jdk_upgrade: bool = False,
) -> dict[str, Any] | None:
    if not full_name:
        return None

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                ac.commit_sha,
                ac.allow_jdk_upgrade,
                ac.declared_java_version,
                ac.effective_java_version,
                ac.build_tool,
                ac.test_framework,
                ac.compiled,
                ac.has_tests,
                ac.tests_passed,
                ac.eliminated,
                ac.error_stage,
                ac.error_summary
            FROM analysis_cache ac
            JOIN repositories r ON r.id = ac.repository_id
            WHERE r.full_name = ?
              AND ac.run_test_suite = ?
              AND ac.allow_jdk_upgrade = ?
            ORDER BY ac.updated_at DESC, ac.id DESC
            LIMIT 1
            """,
            (full_name, bool_int(run_test_suite), bool_int(allow_jdk_upgrade)),
        ).fetchone()

    if row is None:
        return None

    return {
        "commit_sha": row["commit_sha"],
        "allow_jdk_upgrade": bool(row["allow_jdk_upgrade"]),
        "java_version": row["declared_java_version"],
        "effective_java_version": row["effective_java_version"],
        "build": row["build_tool"],
        "test_framework": row["test_framework"],
        "compiled": bool(row["compiled"]),
        "has_tests": bool(row["has_tests"]),
        "tests_passed": bool(row["tests_passed"]),
        "eliminated": bool(row["eliminated"]),
        "error_stage": row["error_stage"],
        "error_message": row["error_summary"],
        "cache_hit": True,
    }


def persist_search_results(
    run_id: int,
    payload: SearchRepositoriesRequest,
    raw_filters: list[GitHubSearchFilterRequest],
    built_filters: list[GitHubSearchFilter],
    repositories: list[dict[str, Any]],
    statistics: dict[str, Any] | None,
    run_test_suite: bool,
) -> None:
    filter_ids = save_search_filters(run_id, raw_filters, built_filters)

    with get_connection() as conn:
        for repo in repositories:
            if not should_persist_repository(
                repo,
                payload.persist_eliminated_repositories,
            ):
                if "compiled" in repo or "eliminated" in repo:
                    repository_id = _upsert_repository(conn, repo)
                    _save_analysis_cache(
                        conn,
                        repository_id,
                        repo,
                        run_test_suite,
                        payload.allow_jdk_upgrade,
                    )
                continue

            repository_id = _upsert_repository(conn, repo)
            run_repository_id = _save_run_repository(
                conn,
                run_id,
                repository_id,
                repo,
                filter_ids,
            )

            if "compiled" in repo or "eliminated" in repo:
                _save_analysis_result(conn, run_repository_id, repo)
                _save_analysis_cache(
                    conn,
                    repository_id,
                    repo,
                    run_test_suite,
                    payload.allow_jdk_upgrade,
                )

    save_statistics(run_id, statistics)


def mined_repositories_to_dicts(repositories: list[MinedRepo]) -> list[dict[str, Any]]:
    return [mined_repo_to_dict(repo) for repo in repositories]
