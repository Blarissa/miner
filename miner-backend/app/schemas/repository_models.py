from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RepoCandidate:
    """Representa um repositório antes das regras finais de análise."""

    full_name: str
    html_url: str
    source_filter: str
    description: str | None = None
    language: str | None = None
    stars: int | None = None
    forks: int | None = None
    open_issues: int | None = None
    topics: list[str] = field(default_factory=list)
    private: bool = False
    fork: bool = False
    archived: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MinedRepo:
    """Resultado de um repositório aprovado pela mineração."""

    repo_name: str
    repo_url: str
    matched_filter: str
    metadata: dict[str, Any] = field(default_factory=dict)
    commit_sha: str | None = None


def mined_repo_from_candidate(
    candidate: RepoCandidate,
    metadata: dict[str, Any] | None = None,
    commit_sha: str | None = None,
) -> MinedRepo:
    return MinedRepo(
        repo_name=candidate.full_name,
        repo_url=candidate.html_url,
        matched_filter=candidate.source_filter,
        metadata=metadata or {},
        commit_sha=commit_sha,
    )


def mined_repo_to_dict(repo: MinedRepo) -> dict[str, Any]:
    data = {
        "repo_name": repo.repo_name,
        "repo_url": repo.repo_url,
        "matched_filter": repo.matched_filter,
        "metadata": repo.metadata,
    }
    if repo.commit_sha:
        data["commit_sha"] = repo.commit_sha
    return data