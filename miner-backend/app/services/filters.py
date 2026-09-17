from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class GitHubSearchType(str, Enum):
    REPOSITORIES = "repositories"
    CODE = "code"


@dataclass
class GitHubSearchFilter:
    """
    Filtro genérico para busca no GitHub.

    A ideia é não tentar mapear todos os qualificadores do GitHub como campos
    Python fixos. O campo `query` recebe a sintaxe oficial do GitHub.
    """

    name: str
    search_type: GitHubSearchType
    query: str

    sort: str | None = None
    order: Literal["asc", "desc"] | None = None
    per_page: int = 100

    # Usado quando a busca encontra código e depois precisamos baixar/analisar arquivo.
    file_path: str | None = None

    # Regras opcionais aplicadas depois da busca, no conteúdo do arquivo.
    content_rules: list[ContentRule] = field(default_factory=list)

    language: str | None = None
    stars: str | None = None
    forks: str | None = None


@dataclass
class ContentRule:
    """
    Regra opcional para validar ou extrair dados de um arquivo encontrado.

    Exemplo:
    - verificar se pom.xml contém Mockito
    - extrair java.version
    - verificar se package.json contém react
    """

    field_name: str
    patterns: list[str]
    required: bool = False
    fixed_value: str | None = None


def qualifier_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()

    text = str(value).strip()
    if not text:
        return None
    if any(char.isspace() for char in text):
        return f'"{text.replace(chr(34), chr(92) + chr(34))}"'
    return text


def append_qualifier(terms: list[str], name: str, value: Any) -> None:
    formatted = qualifier_value(value)
    if formatted is not None:
        terms.append(f"{name}:{formatted}")


def build_search_query(data: dict[str, Any]) -> str:
    terms = [str(data["query"]).strip()]
    search_type = GitHubSearchType(data.get("search_type", "repositories"))

    if search_type == GitHubSearchType.REPOSITORIES and data.get("search_in"):
        append_qualifier(terms, "in", ",".join(data["search_in"]))

    common_qualifier_fields = {
        "user": "user",
        "org": "org",
        "repo": "repo",
    }
    repository_qualifier_fields = {
        "size": "size",
        "stars": "stars",
        "forks": "forks",
        "followers": "followers",
        "created": "created",
        "pushed": "pushed",
        "language": "language",
        "topic": "topic",
        "topics": "topics",
        "license": "license",
        "fork": "fork",
        "archived": "archived",
        "mirror": "mirror",
        "template": "template",
        "good_first_issues": "good-first-issues",
        "help_wanted_issues": "help-wanted-issues",
    }
    code_qualifier_fields = {
        "filename": "filename",
        "extension": "extension",
        "path": "path",
    }

    qualifier_fields = dict(common_qualifier_fields)
    if search_type == GitHubSearchType.CODE:
        qualifier_fields.update(code_qualifier_fields)
    else:
        qualifier_fields.update(repository_qualifier_fields)

    for field_name, qualifier in qualifier_fields.items():
        append_qualifier(terms, qualifier, data.get(field_name))

    if search_type == GitHubSearchType.REPOSITORIES:
        append_qualifier(terms, "is", data.get("visibility"))

    return " ".join(term for term in terms if term)


def filter_from_dict(data: dict[str, Any]) -> GitHubSearchFilter:
    return GitHubSearchFilter(
        name=data["name"],
        search_type=GitHubSearchType(data.get("search_type", "repositories")),
        query=build_search_query(data),
        sort=data.get("sort"),
        order=data.get("order"),
        per_page=int(data.get("per_page", 100)),
        file_path=data.get("file_path"),
        language=data.get("language"),
        stars=data.get("stars"),
        forks=data.get("forks"),
        content_rules=[
            ContentRule(
                field_name=rule["field_name"],
                patterns=rule.get("patterns", []),
                required=rule.get("required", False),
                fixed_value=rule.get("fixed_value"),
            )
            for rule in data.get("content_rules", [])
        ],
    )


def expand_filter_dict(data: dict[str, Any]) -> list[dict[str, Any]]:
    query_values = [data.get("query", ""), *data.get("queries", [])]
    queries: list[str] = []
    for query in query_values:
        text = str(query).strip()
        if text and text not in queries:
            queries.append(text)

    if len(queries) <= 1:
        return [{**data, "query": queries[0] if queries else "", "queries": []}]

    return [
        {
            **data,
            "name": f"{data['name']}-{index}",
            "query": query,
            "queries": [],
        }
        for index, query in enumerate(queries, start=1)
    ]


def filters_from_payload(payload: dict[str, Any]) -> list[GitHubSearchFilter]:
    return [
        filter_from_dict(expanded_item)
        for item in payload.get("filters", [])
        for expanded_item in expand_filter_dict(item)
    ]
