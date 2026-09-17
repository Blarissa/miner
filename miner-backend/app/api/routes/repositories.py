

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.core.config import settings
from app.schemas.repository_requests import RepositoryFilterRequest, SearchRepositoriesRequest
from app.services.filters import filters_from_payload
from app.services.mining_runner import (
    calculate_acceptance_rate,
    calculate_analyzer_batch_size,
    execute_mining_run,
    payload_from_saved_run,
)
from app.services.persistence import (
    cancel_mining_run,
    create_mining_run,
    get_mining_run,
    get_run_repositories,
    get_run_statistics,
    get_search_filters_for_run,
    restart_mining_run,
    save_search_filters,
)


router = APIRouter(prefix="/repositories", tags=["repositories"])
log = logging.getLogger(__name__)


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


def repository_metadata(repo: dict[str, Any]) -> dict[str, Any]:
    value = repo.get("metadata")
    return value if isinstance(value, dict) else {}


def repository_java_version(repo: dict[str, Any]) -> str:
    metadata = repository_metadata(repo)
    return str(repo.get("java_version") or metadata.get("java_version") or "")


def normalize_versions(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    return {str(value).strip()} if str(value).strip() else set()


def optional_payload_bool(value: Any) -> bool | None:
    return None if value is None else payload_bool(value)


def matches_repository_filters(repo: dict[str, Any], filters: dict[str, Any]) -> bool:
    versions = normalize_versions(filters.get("java_versions", filters.get("java_version")))
    if versions and repository_java_version(repo) not in versions:
        return False

    name_filter = str(filters.get("repo_name") or filters.get("name") or "").strip().lower()
    if name_filter and name_filter not in repository_name(repo).lower():
        return False

    eliminated = optional_payload_bool(filters.get("eliminated"))
    if eliminated is not None and payload_bool(repo.get("eliminated")) != eliminated:
        return False
    has_tests = optional_payload_bool(filters.get("has_tests"))
    if has_tests is not None and payload_bool(repo.get("has_tests")) != has_tests:
        return False
    tests_passed = optional_payload_bool(filters.get("tests_passed"))
    if tests_passed is not None and payload_bool(repo.get("tests_passed")) != tests_passed:
        return False
    return True


def run_status_response(run: dict[str, Any]) -> dict[str, Any]:
    response = dict(run)
    response["analyzed_repositories"] = response.get("processed_repositories", 0)
    return response


@router.post("/search", status_code=status.HTTP_202_ACCEPTED)
def search_repositories(payload: SearchRepositoriesRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    payload_data = payload.model_dump()
    token = payload.github_token or settings.github_token
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token nao informado.")

    filters = filters_from_payload(payload_data)
    if not filters:
        raise HTTPException(status_code=400, detail="Nenhum filtro informado.")

    run_id = create_mining_run(payload, status="queued")
    save_search_filters(run_id, payload.filters, filters)
    log.info("Run #%s criado no banco e enfileirado.", run_id)
    background_tasks.add_task(execute_mining_run, run_id, payload, token, filters)
    return {
        "run_id": run_id,
        "status": "queued",
        "status_url": f"/repositories/runs/{run_id}",
        "repositories_url": f"/repositories/runs/{run_id}/repositories",
        "statistics_url": f"/repositories/runs/{run_id}/statistics",
    }


@router.post("/runs/{run_id}/resume", status_code=status.HTTP_202_ACCEPTED)
def resume_repository_run(run_id: int, background_tasks: BackgroundTasks) -> dict[str, Any]:
    run = get_mining_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    if run["status"] in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Run ja esta em execucao.")
    if payload_bool(run.get("exhausted")):
        raise HTTPException(status_code=400, detail="Run ja esgotou as paginas disponiveis.")
    if int(run.get("accepted_repositories", 0)) >= int(run["max_repos"]):
        raise HTTPException(status_code=400, detail="Run ja atingiu a quantidade maxima de repositorios.")

    saved_filters = get_search_filters_for_run(run_id)
    if not saved_filters:
        raise HTTPException(status_code=400, detail="Run nao possui filtros salvos para retomar.")
    token = settings.github_token
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token nao configurado para retomar a run.")

    payload = payload_from_saved_run(run, saved_filters)
    filters = filters_from_payload(payload.model_dump())
    if not filters:
        raise HTTPException(status_code=400, detail="Filtros salvos da run sao invalidos.")

    restart_mining_run(run_id)
    background_tasks.add_task(execute_mining_run, run_id, payload, token, filters, True)
    return {
        "run_id": run_id,
        "status": "queued",
        "resumed": True,
        "status_url": f"/repositories/runs/{run_id}",
        "repositories_url": f"/repositories/runs/{run_id}/repositories",
        "statistics_url": f"/repositories/runs/{run_id}/statistics",
    }


@router.post("/runs/{run_id}/cancel")
def cancel_repository_run(run_id: int) -> dict[str, Any]:
    run = get_mining_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    if run["status"] == "completed":
        raise HTTPException(status_code=400, detail="Run ja foi concluida.")
    cancel_mining_run(run_id)
    return {"run_id": run_id, "status": "cancelled"}


@router.get("/runs/{run_id}")
def get_repository_run(run_id: int) -> dict[str, Any]:
    run = get_mining_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    return run_status_response(run)


@router.get("/runs/{run_id}/repositories")
def get_repository_run_repositories(run_id: int) -> dict[str, Any]:
    run = get_mining_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    repositories = get_run_repositories(run_id)
    return {
        "run_id": run_id,
        "status": run["status"],
        "analyzed_repositories": run.get("processed_repositories", 0),
        "total": len(repositories),
        "repositories": repositories,
    }


@router.get("/runs/{run_id}/statistics")
def get_repository_run_statistics(run_id: int) -> dict[str, Any]:
    run = get_mining_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    statistics = get_run_statistics(run_id)
    return {
        "run_id": run_id,
        "status": run["status"],
        "analyzed_repositories": run.get("processed_repositories", 0),
        "statistics": statistics,
    }


@router.post("/filter")
def filter_repositories(payload: RepositoryFilterRequest) -> dict[str, Any]:
    filters = payload.filters.model_dump(exclude_none=True)
    filtered = [
        repo for repo in payload.repositories
        if isinstance(repo, dict) and matches_repository_filters(repo, filters)
    ]
    return {"total": len(filtered), "repositories": filtered}
