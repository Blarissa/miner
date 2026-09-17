from __future__ import annotations

from typing import Any


def payload_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "sim", "yes", "y"}
    return bool(value)


def should_persist_repository(
    repository: dict[str, Any],
    persist_eliminated_repositories: bool,
) -> bool:
    if persist_eliminated_repositories:
        return True
    return not payload_bool(repository.get("eliminated"))


def filter_persistable_repositories(
    repositories: list[dict[str, Any]],
    persist_eliminated_repositories: bool,
) -> list[dict[str, Any]]:
    return [
        repository
        for repository in repositories
        if should_persist_repository(repository, persist_eliminated_repositories)
    ]
