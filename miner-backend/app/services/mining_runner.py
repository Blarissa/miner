from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from app.schemas.repository_models import MinedRepo, RepoCandidate, mined_repo_to_dict
from app.schemas.repository_requests import SearchRepositoriesRequest
from app.services.filters import GitHubSearchFilter
from app.services.miner import (
    analyze_mined_repositories,
    build_session,
    candidate_key,
    cached_analysis_for_mined_repo,
    fetch_mining_page,
    mine_candidates,
    normalize_java_version,
)
from app.services.persistence import (
    finish_mining_run,
    get_mining_run,
    get_processed_candidate_keys,
    get_run_repositories,
    is_mining_run_cancelled,
    persist_search_results,
    save_statistics,
    update_mining_run_checkpoint,
    update_mining_run_progress,
    upsert_mining_run_candidates_batch,
)
from app.services.statistics import build_statistics


log = logging.getLogger(__name__)
GLOBAL_PIPELINE_SEMAPHORE = threading.BoundedSemaphore(value=1)
MIN_UNPRODUCTIVE_REJECTIONS = 100
UNPRODUCTIVE_REJECTION_FACTOR = 50


class ProgressThrottle:
    def __init__(self, interval_seconds: float = 2.0) -> None:
        self.interval_seconds = interval_seconds
        self.last_write = 0.0

    def should_write(self, force: bool = False) -> bool:
        if force:
            self.last_write = time.monotonic()
            return True

        now = time.monotonic()
        if now - self.last_write < self.interval_seconds:
            return False

        self.last_write = now
        return True


@dataclass
class MiningCursor:
    seen_candidate_keys: set[str]
    page_cursor: int
    per_page: int
    acceptance_rate: float
    last_processed_index: int
    rejected_candidate_count: int

    @classmethod
    def from_run(
        cls,
        run: dict[str, Any] | None,
        *,
        resume: bool,
        existing_eliminated_count: int = 0,
    ) -> "MiningCursor":
        if not resume or run is None:
            return cls(set(), 1, 100, 0.25, 0, 0)

        rejected_candidate_count = max(
            int(run.get("eliminated_repositories", 0)) - existing_eliminated_count,
            0,
        )
        return cls(
            seen_candidate_keys=get_processed_candidate_keys(int(run["id"])),
            page_cursor=int(run.get("page_cursor", 1)),
            per_page=int(run.get("per_page", 100)),
            acceptance_rate=float(run.get("acceptance_rate", 0.25)),
            last_processed_index=int(run.get("last_processed_index", 0)),
            rejected_candidate_count=rejected_candidate_count,
        )

    def total_seen_with_page(self, page_candidates_count: int) -> int:
        return len(self.seen_candidate_keys) + page_candidates_count


def payload_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "sim", "yes", "y"}
    return bool(value)


def repository_name(repo: dict[str, Any]) -> str:
    return str(repo.get("name") or repo.get("repo_name") or "")


def repository_url(repo: dict[str, Any]) -> str:
    return str(repo.get("repository_url") or repo.get("repo_url") or "")


def repository_metadata(repo: dict[str, Any]) -> dict[str, Any]:
    value = repo.get("metadata")
    return value if isinstance(value, dict) else {}


def split_analyzed_results(
    analyzed_results: list[dict[str, Any]],
    payload: SearchRepositoriesRequest,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted_results: list[dict[str, Any]] = []
    eliminated_results: list[dict[str, Any]] = []

    for repo in analyzed_results:
        is_compiled = payload_bool(repo.get("compiled"))
        has_tests = payload_bool(repo.get("has_tests"))
        tests_passed = payload_bool(repo.get("tests_passed"))

        if payload.require_buildable and not is_compiled:
            eliminated_results.append(repo)
            continue
        if payload.require_tests_passed and not (is_compiled and has_tests and tests_passed):
            eliminated_results.append(repo)
            continue
        accepted_results.append(repo)

    return accepted_results, eliminated_results


def cached_results_fill_remaining_slots(
    cached_results: list[dict[str, Any]],
    accepted_count: int,
    payload: SearchRepositoriesRequest,
) -> bool:
    remaining_slots = payload.max_repos - accepted_count
    if remaining_slots <= 0:
        return True

    cached_accepted, _ = split_analyzed_results(cached_results, payload)
    return len(cached_accepted) >= remaining_slots


def should_run_analyzer(payload: SearchRepositoriesRequest) -> bool:
    return payload.analyze or payload.require_buildable or payload.require_tests_passed


def should_run_test_suite(payload: SearchRepositoriesRequest) -> bool:
    return payload.analyze or payload.require_tests_passed


def log_search_filters(run_id: int, filters: list[GitHubSearchFilter]) -> None:
    for index, search_filter in enumerate(filters, start=1):
        log.info(
            "Run #%s | filtro %s/%s | tipo=%s | query=%s",
            run_id,
            index,
            len(filters),
            search_filter.search_type.value,
            search_filter.query,
        )


def is_run_cancelled(run_id: int, message: str) -> bool:
    if not is_mining_run_cancelled(run_id):
        return False
    log.info("Run #%s | %s", run_id, message)
    return True


def update_cursor_checkpoint(
    run_id: int,
    cursor: MiningCursor,
    *,
    batch_size: int,
    exhausted: bool | None = None,
) -> None:
    update_mining_run_checkpoint(
        run_id,
        page_cursor=cursor.page_cursor,
        per_page=cursor.per_page,
        last_processed_index=cursor.last_processed_index,
        acceptance_rate=cursor.acceptance_rate,
        batch_size=batch_size,
        exhausted=exhausted,
    )


def calculate_analyzer_batch_size(max_repos: int, analyzer_workers: int) -> int:
    """Define quantos candidatos entram em cada rodada cara do analyzer."""
    target = max(max_repos, 1)
    workers = max(analyzer_workers, 1)
    if target <= 10:
        batch_size = target * 3
    elif target <= 25:
        batch_size = target * 2
    else:
        batch_size = target
    batch_size = max(batch_size, 10, workers)
    return min(batch_size, 50)


def calculate_acceptance_rate(accepted_count: int, rejected_count: int, previous_rate: float) -> float:
    processed_count = accepted_count + rejected_count
    if processed_count <= 0:
        return previous_rate
    observed_rate = accepted_count / processed_count
    return (previous_rate * 0.7) + (observed_rate * 0.3)


def unproductive_rejection_limit(max_repos: int) -> int:
    return max(MIN_UNPRODUCTIVE_REJECTIONS, max(max_repos, 1) * UNPRODUCTIVE_REJECTION_FACTOR)


def should_stop_unproductive_search(accepted_count: int, rejected_count: int, max_repos: int) -> bool:
    return accepted_count == 0 and rejected_count >= unproductive_rejection_limit(max_repos)


def is_analyzable_java_version(repo: MinedRepo) -> bool:
    version = str(repo.metadata.get("java_version") or "").strip()
    return normalize_java_version(version) is not None


def java_version_rejection_record(repo: MinedRepo) -> dict[str, Any]:
    version = str(repo.metadata.get("java_version") or "").strip()
    metadata = dict(repo.metadata)
    return {
        "name": repo.repo_name,
        "repository_url": repo.repo_url,
        "repo_name": repo.repo_name,
        "repo_url": repo.repo_url,
        "matched_filter": repo.matched_filter,
        "metadata": metadata,
        "commit_sha": repo.commit_sha or metadata.get("commit_sha"),
        "java_version": version,
        "effective_java_version": version,
        "build": metadata.get("build", "Maven"),
        "test_framework": metadata.get("test_framework", ""),
        "compiled": False,
        "has_tests": False,
        "tests_passed": False,
        "eliminated": True,
        "error_stage": "java_version_filter",
        "error_message": "Versão Java ausente ou inválida antes da análise Maven.",
    }


def split_analyzable_repositories(
    repositories: list[MinedRepo],
) -> tuple[list[MinedRepo], list[dict[str, Any]]]:
    analyzable: list[MinedRepo] = []
    rejected: list[dict[str, Any]] = []
    for repo in repositories:
        if is_analyzable_java_version(repo):
            analyzable.append(repo)
        else:
            rejected.append(java_version_rejection_record(repo))
    return analyzable, rejected


def content_filter_rejection_record(
    *, page_cursor: int, page_index: int, candidate: RepoCandidate, search_filter: GitHubSearchFilter
) -> dict[str, Any]:
    return {
        "page_number": page_cursor,
        "page_index": page_index,
        "repo_full_name": candidate.full_name,
        "repo_url": candidate.html_url,
        "matched_filter": search_filter.name,
        "matched_file": candidate.raw.get("_matched_path"),
        "status": "rejected",
        "rejection_stage": "content_filter",
        "metadata": candidate.raw,
    }


def mined_candidate_record(
    *, page_cursor: int, page_index: int, repo: MinedRepo, accepted: bool
) -> dict[str, Any]:
    return {
        "page_number": page_cursor,
        "page_index": page_index,
        "repo_full_name": repo.repo_name,
        "repo_url": repo.repo_url,
        "commit_sha": repo.commit_sha,
        "matched_filter": repo.matched_filter,
        "matched_file": repo.metadata.get("matched_file"),
        "status": "accepted" if accepted else "rejected",
        "rejection_stage": None if accepted else "max_repos_reached",
        "metadata": repo.metadata,
    }


def analyzed_candidate_record(
    *, page_cursor: int, page_index: int, repo: dict[str, Any], accepted: bool, overflow: bool
) -> dict[str, Any]:
    metadata = repository_metadata(repo)
    return {
        "page_number": page_cursor,
        "page_index": page_index,
        "repo_full_name": repository_name(repo),
        "repo_url": repository_url(repo),
        "commit_sha": repo.get("commit_sha"),
        "matched_filter": repo.get("matched_filter"),
        "matched_file": metadata.get("matched_file"),
        "status": "accepted" if accepted else "rejected",
        "rejection_stage": None if accepted else ("max_repos_reached" if overflow else repo.get("error_stage")),
        "error_message": None if accepted else repo.get("error_message"),
        "metadata": metadata,
    }


def payload_from_saved_run(run: dict[str, Any], filters: list[Any]) -> SearchRepositoriesRequest:
    return SearchRepositoriesRequest(
        github_token=None,
        max_repos=int(run["max_repos"]),
        max_workers=int(run["max_workers"]),
        analyzer_workers=int(run["analyzer_workers"]),
        delay=float(run["delay_seconds"]),
        analyze=payload_bool(run.get("analyze")),
        require_buildable=payload_bool(run.get("require_buildable")),
        require_tests_passed=payload_bool(run.get("require_tests_passed")),
        allow_jdk_upgrade=payload_bool(run.get("allow_jdk_upgrade")),
        persist_eliminated_repositories=payload_bool(run.get("persist_eliminated_repositories")),
        include_statistics=payload_bool(run.get("include_statistics"), True),
        statistics_scope=run.get("statistics_scope") or "accepted",
        filters=filters,
    )


def execute_mining_run(
    run_id: int,
    payload: SearchRepositoriesRequest,
    token: str,
    filters: list[GitHubSearchFilter],
    resume: bool = False,
) -> None:
    started_at = time.perf_counter()
    progress_throttle = ProgressThrottle()
    log.info("Run #%s | aguardando vaga no throttling global.", run_id)
    GLOBAL_PIPELINE_SEMAPHORE.acquire()
    log.info("Run #%s | vaga obtida no throttling global.", run_id)

    try:
        session = build_session(token)
        saved_run = get_mining_run(run_id) if resume else None
        update_mining_run_progress(run_id, status="running", progress_stage="mining")
        log.info(
            "Busca iniciada | max_repos=%s | max_workers=%s | analyzer_workers=%s | "
            "require_buildable=%s | require_tests_passed=%s | allow_jdk_upgrade=%s | persist_eliminated=%s",
            payload.max_repos, payload.max_workers, payload.analyzer_workers,
            payload.require_buildable, payload.require_tests_passed,
            payload.allow_jdk_upgrade,
            payload.persist_eliminated_repositories,
        )
        log_search_filters(run_id, filters)

        if should_run_analyzer(payload):
            run_test_suite = should_run_test_suite(payload)
            existing_results = get_run_repositories(run_id) if resume else []
            analyzed_results = list(existing_results)
            accepted_results, eliminated_results = split_analyzed_results(analyzed_results, payload)
            cursor = MiningCursor.from_run(saved_run, resume=resume, existing_eliminated_count=len(eliminated_results))
            analyzer_batch_size = calculate_analyzer_batch_size(payload.max_repos, payload.analyzer_workers)
            log.info("Run #%s | analyzer batch_size=%s calculado por max_repos=%s.", run_id, analyzer_batch_size, payload.max_repos)
            update_cursor_checkpoint(run_id, cursor, batch_size=analyzer_batch_size, exhausted=False)

            while len(accepted_results) < payload.max_repos:
                if is_run_cancelled(run_id, "cancelada antes de buscar nova pagina."):
                    return
                update_mining_run_progress(run_id, progress_stage="mining")
                update_cursor_checkpoint(run_id, cursor, batch_size=analyzer_batch_size)
                mining_page = fetch_mining_page(
                    token=token, filters=filters, page=cursor.page_cursor,
                    per_page=cursor.per_page, delay=payload.delay,
                    seen_keys=cursor.seen_candidate_keys, session=session,
                )
                update_mining_run_progress(run_id, progress_stage="mined", total_candidates=cursor.total_seen_with_page(len(mining_page.candidates)))
                if not mining_page.candidates:
                    if mining_page.has_next_page:
                        cursor.page_cursor += 1
                        cursor.last_processed_index = 0
                        update_cursor_checkpoint(run_id, cursor, batch_size=analyzer_batch_size)
                        continue
                    update_cursor_checkpoint(run_id, cursor, batch_size=analyzer_batch_size, exhausted=True)
                    break

                for start in range(0, len(mining_page.candidates), analyzer_batch_size):
                    if is_run_cancelled(run_id, "cancelada antes de processar novo chunk."):
                        return
                    if len(accepted_results) >= payload.max_repos:
                        break
                    candidate_batch = mining_page.candidates[start:start + analyzer_batch_size]
                    mined_batch_results = mine_candidates(token=token, page_candidates=candidate_batch, max_workers=payload.max_workers, delay=payload.delay)
                    mined_keys = {key for _, key, _ in mined_batch_results}
                    max_processed_index = max(page_index for page_index, _, _ in candidate_batch) + 1
                    candidate_records: list[dict[str, Any]] = []
                    for page_index, candidate, search_filter in candidate_batch:
                        key = candidate_key(candidate)
                        if key in mined_keys:
                            continue
                        cursor.seen_candidate_keys.add(key)
                        cursor.rejected_candidate_count += 1
                        candidate_records.append(content_filter_rejection_record(page_cursor=cursor.page_cursor, page_index=page_index, candidate=candidate, search_filter=search_filter))

                    batch_repositories = [repo for _, _, repo in mined_batch_results]
                    analyzable_repositories, pre_rejected_results = split_analyzable_repositories(batch_repositories)
                    page_index_by_url = {repo.repo_url: page_index for page_index, _, repo in mined_batch_results}
                    key_by_url = {repo.repo_url: key for _, key, repo in mined_batch_results}
                    if progress_throttle.should_write():
                        update_mining_run_progress(run_id, progress_stage="analyzing", eliminated_repositories=len(eliminated_results) + cursor.rejected_candidate_count)
                    log.info("Run #%s | pagina=%s | chunk=%s-%s | minerados=%s | analyzer iniciado.", run_id, cursor.page_cursor, start, max_processed_index, len(batch_repositories))

                    if not batch_repositories:
                        upsert_mining_run_candidates_batch(run_id, candidate_records)
                        cursor.last_processed_index = max_processed_index
                        update_cursor_checkpoint(run_id, cursor, batch_size=analyzer_batch_size)
                        if progress_throttle.should_write(force=True):
                            update_mining_run_progress(run_id, processed_repositories=len(analyzed_results), accepted_repositories=len(accepted_results), eliminated_repositories=len(eliminated_results) + cursor.rejected_candidate_count)
                        if should_stop_unproductive_search(
                            len(accepted_results),
                            len(eliminated_results) + cursor.rejected_candidate_count,
                            payload.max_repos,
                        ):
                            log.warning(
                                "Run #%s | encerrando busca: %s rejeicoes e nenhum aceito.",
                                run_id,
                                len(eliminated_results) + cursor.rejected_candidate_count,
                            )
                            update_cursor_checkpoint(run_id, cursor, batch_size=analyzer_batch_size, exhausted=True)
                            break
                        continue

                    if pre_rejected_results:
                        log.info(
                            "Run #%s | rejeicao precoce por java_version invalida: %s/%s.",
                            run_id,
                            len(pre_rejected_results),
                            len(batch_repositories),
                        )

                    cached_analyzed: list[dict[str, Any]] = []
                    pending_analyzable_repositories: list[MinedRepo] = []
                    for repo in analyzable_repositories:
                        cached_result = cached_analysis_for_mined_repo(
                            repo,
                            run_test_suite,
                            payload.allow_jdk_upgrade,
                        )
                        if cached_result is None:
                            pending_analyzable_repositories.append(repo)
                        else:
                            cached_analyzed.append(cached_result)

                    if pending_analyzable_repositories and not cached_results_fill_remaining_slots(
                        cached_analyzed,
                        len(accepted_results),
                        payload,
                    ):
                        new_analyzed = analyze_mined_repositories(
                            repositories=pending_analyzable_repositories,
                            max_workers=payload.analyzer_workers,
                            run_test_suite=run_test_suite,
                            allow_jdk_upgrade=payload.allow_jdk_upgrade,
                        )
                    else:
                        if pending_analyzable_repositories:
                            log.info(
                                "Run #%s | %s repositorios pendentes pulados: cache ja preencheu max_repos.",
                                run_id,
                                len(pending_analyzable_repositories),
                            )
                        new_analyzed = []

                    batch_analyzed = cached_analyzed + new_analyzed
                    batch_analyzed = pre_rejected_results + batch_analyzed
                    analyzed_results.extend(batch_analyzed)
                    batch_accepted, batch_eliminated = split_analyzed_results(batch_analyzed, payload)
                    remaining_slots = payload.max_repos - len(accepted_results)
                    accepted_to_keep = batch_accepted[:remaining_slots]
                    overflow_accepted = batch_accepted[remaining_slots:]
                    accepted_results.extend(accepted_to_keep)
                    eliminated_results.extend(batch_eliminated)
                    persist_search_results(run_id=run_id, payload=payload, raw_filters=payload.filters, built_filters=filters, repositories=accepted_to_keep + batch_eliminated, statistics=None, run_test_suite=run_test_suite)
                    accepted_urls = {repository_url(repo) for repo in accepted_to_keep}
                    overflow_urls = {repository_url(repo) for repo in overflow_accepted}
                    for repo in batch_analyzed:
                        repo_url_value = repository_url(repo)
                        is_accepted = repo_url_value in accepted_urls
                        cursor.seen_candidate_keys.add(key_by_url.get(repo_url_value, repository_name(repo)))
                        candidate_records.append(analyzed_candidate_record(page_cursor=cursor.page_cursor, page_index=page_index_by_url.get(repo_url_value, 0), repo=repo, accepted=is_accepted, overflow=repo_url_value in overflow_urls))
                    upsert_mining_run_candidates_batch(run_id, candidate_records)
                    cursor.acceptance_rate = calculate_acceptance_rate(len(accepted_results), len(eliminated_results) + cursor.rejected_candidate_count, cursor.acceptance_rate)
                    cursor.last_processed_index = max_processed_index
                    update_cursor_checkpoint(run_id, cursor, batch_size=analyzer_batch_size)
                    if progress_throttle.should_write(force=True):
                        update_mining_run_progress(run_id, processed_repositories=len(analyzed_results), accepted_repositories=len(accepted_results), eliminated_repositories=len(eliminated_results) + cursor.rejected_candidate_count)
                    if should_stop_unproductive_search(
                        len(accepted_results),
                        len(eliminated_results) + cursor.rejected_candidate_count,
                        payload.max_repos,
                    ):
                        log.warning(
                            "Run #%s | encerrando busca: %s rejeicoes e nenhum aceito.",
                            run_id,
                            len(eliminated_results) + cursor.rejected_candidate_count,
                        )
                        update_cursor_checkpoint(run_id, cursor, batch_size=analyzer_batch_size, exhausted=True)
                        break

                if len(accepted_results) >= payload.max_repos:
                    break
                if should_stop_unproductive_search(
                    len(accepted_results),
                    len(eliminated_results) + cursor.rejected_candidate_count,
                    payload.max_repos,
                ):
                    break
                if not mining_page.has_next_page:
                    update_cursor_checkpoint(run_id, cursor, batch_size=analyzer_batch_size, exhausted=True)
                    break
                cursor.page_cursor += 1
                cursor.last_processed_index = 0
                update_cursor_checkpoint(run_id, cursor, batch_size=analyzer_batch_size)

            log.info("Run #%s | etapa analyzer concluida | analisados=%s.", run_id, len(analyzed_results))
            log.info("Run #%s | calculando estatisticas.", run_id)
            update_mining_run_progress(run_id, progress_stage="building_statistics", processed_repositories=len(analyzed_results))
            statistics = build_statistics(analyzed_results, payload.statistics_scope) if payload.include_statistics else None
            update_mining_run_progress(run_id, accepted_repositories=len(accepted_results), eliminated_repositories=len(eliminated_results) + cursor.rejected_candidate_count)
            response_repositories = accepted_results + eliminated_results if payload.persist_eliminated_repositories else accepted_results
            log.info("Run #%s | filtro final aplicado | aceitos=%s | eliminados=%s | total_resposta=%s.", run_id, len(accepted_results), len(eliminated_results), len(response_repositories))
            log.info("Run #%s | persistencia iniciada.", run_id)
            update_mining_run_progress(run_id, progress_stage="persisting")
            save_statistics(run_id, statistics)
            log.info("Run #%s | persistencia concluida.", run_id)
            if is_mining_run_cancelled(run_id):
                log.info("Run #%s | cancelada antes de finalizar.", run_id)
                return
            finish_mining_run(run_id)
            log.info("Run #%s | busca concluida | total_resposta=%s | tempo=%.1fs.", run_id, len(analyzed_results), time.perf_counter() - started_at)
            return

        log.info("Run #%s | mineracao incremental iniciada sem analyzer.", run_id)
        existing_mined_results = get_run_repositories(run_id) if resume else []
        repositories = list(existing_mined_results)
        cursor = MiningCursor.from_run(saved_run, resume=resume)
        mining_batch_size = calculate_analyzer_batch_size(payload.max_repos, payload.max_workers)
        update_cursor_checkpoint(run_id, cursor, batch_size=mining_batch_size, exhausted=False)

        while len(repositories) < payload.max_repos:
            if is_run_cancelled(run_id, "cancelada antes de buscar nova pagina."):
                return
            update_mining_run_progress(run_id, progress_stage="mining")
            mining_page = fetch_mining_page(token=token, filters=filters, page=cursor.page_cursor, per_page=cursor.per_page, delay=payload.delay, seen_keys=cursor.seen_candidate_keys, session=session)
            update_mining_run_progress(run_id, progress_stage="mined", total_candidates=cursor.total_seen_with_page(len(mining_page.candidates)))
            if not mining_page.candidates:
                if mining_page.has_next_page:
                    cursor.page_cursor += 1
                    cursor.last_processed_index = 0
                    update_cursor_checkpoint(run_id, cursor, batch_size=mining_batch_size)
                    continue
                update_cursor_checkpoint(run_id, cursor, batch_size=mining_batch_size, exhausted=True)
                break

            for start in range(0, len(mining_page.candidates), mining_batch_size):
                if is_run_cancelled(run_id, "cancelada antes de processar novo chunk."):
                    return
                if len(repositories) >= payload.max_repos:
                    break
                candidate_batch = mining_page.candidates[start:start + mining_batch_size]
                mined_batch_results = mine_candidates(token=token, page_candidates=candidate_batch, max_workers=payload.max_workers, delay=payload.delay)
                mined_keys = {key for _, key, _ in mined_batch_results}
                max_processed_index = max(page_index for page_index, _, _ in candidate_batch) + 1
                candidate_records: list[dict[str, Any]] = []
                for page_index, candidate, search_filter in candidate_batch:
                    key = candidate_key(candidate)
                    if key in mined_keys:
                        continue
                    cursor.seen_candidate_keys.add(key)
                    cursor.rejected_candidate_count += 1
                    candidate_records.append(content_filter_rejection_record(page_cursor=cursor.page_cursor, page_index=page_index, candidate=candidate, search_filter=search_filter))
                remaining_slots = payload.max_repos - len(repositories)
                mined_to_keep = [repo for _, _, repo in mined_batch_results[:remaining_slots]]
                overflow_results = mined_batch_results[remaining_slots:]
                mined_result_dicts = [mined_repo_to_dict(repo) for repo in mined_to_keep]
                repositories.extend(mined_result_dicts)
                persist_search_results(run_id=run_id, payload=payload, raw_filters=payload.filters, built_filters=filters, repositories=mined_result_dicts, statistics=None, run_test_suite=False)
                for page_index, key, repo in mined_batch_results:
                    cursor.seen_candidate_keys.add(key)
                    candidate_records.append(mined_candidate_record(page_cursor=cursor.page_cursor, page_index=page_index, repo=repo, accepted=repo in mined_to_keep))
                upsert_mining_run_candidates_batch(run_id, candidate_records)
                cursor.acceptance_rate = calculate_acceptance_rate(len(repositories), cursor.rejected_candidate_count + len(overflow_results), cursor.acceptance_rate)
                cursor.last_processed_index = max_processed_index
                update_cursor_checkpoint(run_id, cursor, batch_size=mining_batch_size)
                if progress_throttle.should_write(force=True):
                    update_mining_run_progress(run_id, processed_repositories=len(cursor.seen_candidate_keys), accepted_repositories=len(repositories), eliminated_repositories=cursor.rejected_candidate_count + len(overflow_results))
                if should_stop_unproductive_search(
                    len(repositories),
                    cursor.rejected_candidate_count + len(overflow_results),
                    payload.max_repos,
                ):
                    log.warning(
                        "Run #%s | encerrando mineracao: %s rejeicoes e nenhum aceito.",
                        run_id,
                        cursor.rejected_candidate_count + len(overflow_results),
                    )
                    update_cursor_checkpoint(run_id, cursor, batch_size=mining_batch_size, exhausted=True)
                    break

            if len(repositories) >= payload.max_repos:
                break
            if should_stop_unproductive_search(
                len(repositories),
                cursor.rejected_candidate_count,
                payload.max_repos,
            ):
                break
            if not mining_page.has_next_page:
                update_cursor_checkpoint(run_id, cursor, batch_size=mining_batch_size, exhausted=True)
                break
            cursor.page_cursor += 1
            cursor.last_processed_index = 0
            update_cursor_checkpoint(run_id, cursor, batch_size=mining_batch_size)

        log.info("Run #%s | mineracao incremental concluida | repositorios=%s.", run_id, len(repositories))
        update_mining_run_progress(run_id, progress_stage="building_statistics", total_candidates=len(cursor.seen_candidate_keys), processed_repositories=len(cursor.seen_candidate_keys), accepted_repositories=len(repositories), eliminated_repositories=cursor.rejected_candidate_count)
        response: dict[str, Any] = {"run_id": run_id, "total": len(repositories), "repositories": repositories}
        if payload.include_statistics:
            log.info("Run #%s | calculando estatisticas.", run_id)
            response["statistics"] = build_statistics(repositories, payload.statistics_scope)
        log.info("Run #%s | persistencia iniciada.", run_id)
        update_mining_run_progress(run_id, progress_stage="persisting")
        save_statistics(run_id, response.get("statistics"))
        log.info("Run #%s | persistencia concluida.", run_id)
        if is_mining_run_cancelled(run_id):
            log.info("Run #%s | cancelada antes de finalizar.", run_id)
            return
        finish_mining_run(run_id)
        log.info("Run #%s | busca concluida | total_resposta=%s | tempo=%.1fs.", run_id, len(repositories), time.perf_counter() - started_at)
    except Exception as exc:
        finish_mining_run(run_id, "failed", str(exc))
        log.exception("Run #%s | busca falhou: %s", run_id, exc)
    finally:
        GLOBAL_PIPELINE_SEMAPHORE.release()
        log.info("Run #%s | vaga liberada no throttling global.", run_id)
