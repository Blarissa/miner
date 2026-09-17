from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ContentRuleRequest(BaseModel):
    field_name: str = Field(examples=["java_version"])
    patterns: list[str] = Field(default_factory=list)
    required: bool = False
    fixed_value: str | None = None


class GitHubSearchFilterRequest(BaseModel):
    name: str
    search_type: Literal["repositories", "code"] = "code"
    query: str = ""
    queries: list[str] = Field(default_factory=list)
    search_in: list[Literal["name", "description", "readme", "topics"]] | None = None
    user: str | None = None
    org: str | None = None
    repo: str | None = None
    size: str | None = None
    stars: str | None = None
    forks: str | None = None
    followers: str | None = None
    created: str | None = None
    pushed: str | None = None
    language: str | None = None
    topic: str | None = None
    topics: str | None = None
    license: str | None = None
    visibility: Literal["public", "private", "internal"] | None = None
    fork: Literal["true", "false", "only"] | None = None
    archived: bool | None = None
    mirror: bool | None = None
    template: bool | None = None
    good_first_issues: str | None = None
    help_wanted_issues: str | None = None
    filename: str | None = None
    extension: str | None = None
    path: str | None = None
    sort: str | None = None
    order: Literal["asc", "desc"] | None = None
    per_page: int = Field(default=100, ge=1, le=100)
    file_path: str | None = None
    content_rules: list[ContentRuleRequest] = Field(default_factory=list)

    @field_validator("size", "stars", "forks", "followers", "topics")
    @classmethod
    def validate_non_negative_range(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        numbers = [int(match) for match in re.findall(r"-?\d+", text)]
        if any(number < 0 for number in numbers):
            raise ValueError("Use apenas valores maiores ou iguais a 0.")
        return text

    @field_validator("created", "pushed")
    @classmethod
    def normalize_brazilian_dates(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None

        def convert(match: re.Match[str]) -> str:
            parsed = datetime.strptime(match.group(0), "%d/%m/%Y")
            return parsed.strftime("%Y-%m-%d")

        return re.sub(r"\b\d{2}/\d{2}/\d{4}\b", convert, text)

    @model_validator(mode="after")
    def validate_query_values(self) -> GitHubSearchFilterRequest:
        queries = [query.strip() for query in self.queries if query.strip()]
        query = self.query.strip()
        if not query and not queries:
            raise ValueError("Informe pelo menos uma query.")
        self.query = query
        self.queries = queries
        return self


class RepositoryFilterOptions(BaseModel):
    java_version: str | None = None
    java_versions: list[str] | None = None
    repo_name: str | None = None
    eliminated: bool | None = None
    has_tests: bool | None = None
    tests_passed: bool | None = None


class RepositoryFilterRequest(BaseModel):
    repositories: list[dict[str, Any]]
    filters: RepositoryFilterOptions = Field(default_factory=RepositoryFilterOptions)


class SearchRepositoriesRequest(BaseModel):
    github_token: str | None = None
    max_repos: int = Field(default=100, ge=1, le=5000)
    max_workers: int = Field(default=5, ge=1, le=20)
    analyzer_workers: int = Field(default=4, ge=1, le=8)
    delay: float = Field(default=0.0, ge=0)
    analyze: bool = False
    require_buildable: bool = False
    require_tests_passed: bool = False
    allow_jdk_upgrade: bool = False
    persist_eliminated_repositories: bool = False
    include_statistics: bool = True
    statistics_scope: Literal["all", "accepted", "eliminated"] = "accepted"
    filters: list[GitHubSearchFilterRequest] = Field(default_factory=list)

    @model_validator(mode="after")
    def expand_multi_query_filters(self) -> SearchRepositoriesRequest:
        expanded_filters: list[GitHubSearchFilterRequest] = []
        for search_filter in self.filters:
            query_values = [search_filter.query, *search_filter.queries]
            queries: list[str] = []
            for query in query_values:
                trimmed = query.strip()
                if trimmed and trimmed not in queries:
                    queries.append(trimmed)

            if len(queries) <= 1:
                expanded_filters.append(
                    search_filter.model_copy(update={"query": queries[0], "queries": []})
                )
                continue

            for index, query in enumerate(queries, start=1):
                expanded_filters.append(
                    search_filter.model_copy(
                        update={
                            "name": f"{search_filter.name}-{index}",
                            "query": query,
                            "queries": [],
                        }
                    )
                )

        self.filters = expanded_filters
        return self
