from __future__ import annotations

import base64
import logging
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote

from app.core import config

import requests

from app.services.filters import ContentRule, GitHubSearchFilter, GitHubSearchType
from app.schemas.repository_models import MinedRepo, RepoCandidate, mined_repo_from_candidate

log = logging.getLogger(__name__)
_worker_state = threading.local()
_etag_cache: dict[str, tuple[str, requests.Response]] = {}
_etag_lock = threading.Lock()

HTTP_MAX_ATTEMPTS = 4
HTTP_REQUEST_BUDGET_SECONDS = 90
HTTP_REQUEST_TIMEOUT_SECONDS = 20
RETRYABLE_STATUS_CODES = {403, 429}
IGNORED_STATUS_CODES = {404, 422}
BACKOFF_JITTER_SECONDS = 0.25
GITHUB_SEARCH_RESULT_LIMIT = 1000


class TokenRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._blocked_until: dict[str, float] = {}

    def wait(self, token: str) -> None:
        with self._lock:
            wait = max(self._blocked_until.get(token, 0.0) - time.monotonic(), 0.0)
        if wait > 0:
            time.sleep(wait)

    def block(self, token: str, seconds: int) -> None:
        if seconds <= 0:
            return
        blocked_until = time.monotonic() + seconds
        with self._lock:
            self._blocked_until[token] = max(
                self._blocked_until.get(token, 0.0),
                blocked_until,
            )


_rate_limiter = TokenRateLimiter()

REPOSITORY_SEARCH_URL = f"{config.settings.github_base_url}/search/repositories"
CODE_SEARCH_URL = f"{config.settings.github_base_url}/search/code"
REPOSITORY_URL = f"{config.settings.github_base_url}/repos/{{full_name}}"
CONTENTS_URL = f"{config.settings.github_base_url}/repos/{{full_name}}/contents/{{path}}"
COMMITS_URL = f"{config.settings.github_base_url}/repos/{{full_name}}/commits/{{ref}}"
ROOT_POM_PATH = "pom.xml"
MAIN_JAVA_PATH = "src/main/java"
MAX_MAIN_SOURCE_FILES_TO_CHECK = 200

JAVA_VERSION_PATTERNS = [
    r"<maven\.compiler\.release>\s*([0-9][0-9.]*)\s*</maven\.compiler\.release>",
    r"<maven\.compiler\.source>\s*([0-9][0-9.]*)\s*</maven\.compiler\.source>",
    r"<maven\.compiler\.target>\s*([0-9][0-9.]*)\s*</maven\.compiler\.target>",
    r"<java\.version>\s*([0-9][0-9.]*)\s*</java\.version>",
    r"<jdk\.version>\s*([0-9][0-9.]*)\s*</jdk\.version>",
    r"<release>\s*([0-9][0-9.]*)\s*</release>",
    r"<source>\s*([0-9][0-9.]*)\s*</source>",
    r"<target>\s*([0-9][0-9.]*)\s*</target>",
]


@dataclass
class MiningPage:
    candidates: list[tuple[int, RepoCandidate, GitHubSearchFilter]]
    total_count: int
    has_next_page: bool


def format_github_date_to_br(value: Any) -> str:
    if not value:
        return ""

    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return str(value)

    return parsed.strftime("%d/%m/%Y")


def build_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": config.settings.github_api_version,
        }
    )
    return session


def worker_session(token: str) -> requests.Session:
    session = getattr(_worker_state, "session", None)
    if session is None:
        session = build_session(token)
        _worker_state.session = session
    return session


def int_header(resp: requests.Response, name: str) -> int | None:
    value = resp.headers.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def handle_rate_limit(
    resp: requests.Response,
    token: str,
    fallback_wait: int = 60,
) -> bool:
    retry_after = int_header(resp, "Retry-After")
    if retry_after is not None and retry_after > 0:
        log.warning("GitHub pediu Retry-After=%ss. Aguardando.", retry_after)
        _rate_limiter.block(token, retry_after)
        return True

    remaining = int_header(resp, "X-RateLimit-Remaining")
    reset_ts = int_header(resp, "X-RateLimit-Reset")
    body = resp.text.lower()

    if remaining == 0 and reset_ts is not None:
        wait = max(reset_ts - int(time.time()), 0) + 5
        log.warning("Rate limit do GitHub esgotado. Aguardando %ss.", wait)
        _rate_limiter.block(token, wait)
        return True

    if "secondary rate limit" in body or "abuse detection" in body:
        log.warning("Rate limit secundario do GitHub. Aguardando %ss.", fallback_wait)
        _rate_limiter.block(token, fallback_wait)
        return True

    if resp.status_code == 429:
        log.warning("GitHub retornou 429 sem Retry-After. Aguardando %ss.", fallback_wait)
        _rate_limiter.block(token, fallback_wait)
        return True

    return False


def safe_get(
    session: requests.Session,
    url: str,
    params: dict[str, Any] | None = None,
    delay: float = 0.0,
) -> requests.Response | None:
    cache_key = requests.Request("GET", url, params=params).prepare().url or url
    token = str(session.headers.get("Authorization", ""))
    deadline = time.monotonic() + HTTP_REQUEST_BUDGET_SECONDS

    for attempt in range(HTTP_MAX_ATTEMPTS):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        _rate_limiter.wait(token)
        try:
            headers: dict[str, str] = {}
            with _etag_lock:
                cached = _etag_cache.get(cache_key)
            if cached is not None:
                headers["If-None-Match"] = cached[0]

            resp = session.get(
                url,
                params=params,
                headers=headers,
                timeout=min(HTTP_REQUEST_TIMEOUT_SECONDS, max(remaining, 1)),
            )

            cached_response = response_from_cache(cache_key, resp, cached, token)
            if cached_response is not None:
                return cached_response

            if resp.status_code in RETRYABLE_STATUS_CODES:
                if not handle_rate_limit(resp, token, fallback_wait=max(int(delay), 1) * 60):
                    log.warning(
                        "HTTP %s em %s sem sinal claro de rate limit (tentativa %s/4)",
                        resp.status_code,
                        resp.url,
                        attempt + 1,
                    )
                    sleep_with_backoff(attempt)
                continue

            if resp.status_code in IGNORED_STATUS_CODES:
                log.debug("HTTP %s em %s", resp.status_code, resp.url)
                return None

            log.warning(
                "HTTP %s em %s (tentativa %s/4)",
                resp.status_code,
                resp.url,
                attempt + 1,
            )
            sleep_with_backoff(attempt)

        except requests.exceptions.RequestException as exc:
            log.warning("Erro de rede em %s: %s (tentativa %s/4)", url, exc, attempt + 1)
            sleep_with_backoff(attempt)

    log.error("Desistindo apos 4 tentativas: %s", url)
    return None


def response_from_cache(
    cache_key: str,
    resp: requests.Response,
    cached: tuple[str, requests.Response] | None,
    token: str,
) -> requests.Response | None:
    if resp.status_code == 200:
        handle_rate_limit(resp, token)
        store_response_cache(cache_key, resp)
        return resp

    if resp.status_code == 304 and cached is not None:
        log.debug("GitHub 304 cache hit: %s", cache_key)
        return cached[1]

    return None


def store_response_cache(cache_key: str, resp: requests.Response) -> None:
    etag = resp.headers.get("ETag")
    if not etag:
        return

    with _etag_lock:
        _etag_cache[cache_key] = (etag, resp)


def sleep_with_backoff(attempt: int) -> None:
    time.sleep((2**attempt) + random.uniform(0, BACKOFF_JITTER_SECONDS))


def repo_meta_to_candidate(repo_meta: dict[str, Any], source_filter: str) -> RepoCandidate:
    return RepoCandidate( 
        full_name=repo_meta.get("full_name", ""),
        html_url=repo_meta.get("html_url", ""),
        source_filter=source_filter,
        description=repo_meta.get("description"),
        language=repo_meta.get("language"),
        stars=repo_meta.get("stargazers_count"),
        forks=repo_meta.get("forks_count"),
        open_issues=repo_meta.get("open_issues_count"),
        topics=repo_meta.get("topics", []),
        private=repo_meta.get("private", False),
        fork=repo_meta.get("fork", False),
        archived=repo_meta.get("archived", False),
        raw=dict(repo_meta),
    )


def candidate_key(candidate: RepoCandidate) -> str:
    return candidate.full_name


def merge_candidate_metadata(existing: RepoCandidate, candidate: RepoCandidate) -> None:
    matches = existing.raw.setdefault("_matches", [])
    if not isinstance(matches, list):
        matches = []
        existing.raw["_matches"] = matches

    matched_path = candidate.raw.get("_matched_path")
    if matched_path and matched_path not in {
        item.get("path") for item in matches if isinstance(item, dict)
    }:
        matches.append(
            {
                "path": matched_path,
                "html_url": candidate.raw.get("_matched_file_url"),
                "source_filter": candidate.source_filter,
            }
        )


def is_usable_candidate(candidate: RepoCandidate) -> bool:
    return bool(candidate.full_name) and not (
        candidate.private or candidate.fork or candidate.archived
    )


def numeric_filter_matches(actual: int | None, expression: str | None) -> bool:
    if expression is None or not expression.strip():
        return True
    if actual is None:
        return False

    value = expression.strip()
    match = re.match(r"^(>=|<=|>|<)?\s*(\d+)$", value)
    if not match:
        return True

    operator = match.group(1) or "=="
    expected = int(match.group(2))

    if operator == ">=":
        return actual >= expected
    if operator == "<=":
        return actual <= expected
    if operator == ">":
        return actual > expected
    if operator == "<":
        return actual < expected
    return actual == expected


def candidate_matches_metadata_filter(
    candidate: RepoCandidate,
    search_filter: GitHubSearchFilter,
) -> bool:
    if search_filter.language:
        candidate_language = (candidate.language or "").strip().lower()
        expected_language = search_filter.language.strip().lower()
        if candidate_language != expected_language:
            return False

    return (
        numeric_filter_matches(candidate.stars, search_filter.stars)
        and numeric_filter_matches(candidate.forks, search_filter.forks)
    )


def metadata_filter_requested(search_filter: GitHubSearchFilter) -> bool:
    return bool(search_filter.language or search_filter.stars or search_filter.forks)


def has_required_metadata(
    candidate: RepoCandidate,
    search_filter: GitHubSearchFilter,
) -> bool:
    if search_filter.language and not candidate.language:
        return False
    if search_filter.stars and candidate.stars is None:
        return False
    if search_filter.forks and candidate.forks is None:
        return False
    return True


def fetch_repository_metadata(
    session: requests.Session,
    full_name: str,
    delay: float,
) -> dict[str, Any] | None:
    if not full_name:
        return None

    url = REPOSITORY_URL.format(full_name=quote(full_name, safe="/"))
    resp = safe_get(session, url, delay=delay)
    if resp is None:
        return None

    return resp.json()


def preserve_code_search_match_metadata(
    original: RepoCandidate,
    enriched: RepoCandidate,
) -> RepoCandidate:
    for key in ("_matched_path", "_matched_file_url", "_matches"):
        if key in original.raw:
            enriched.raw[key] = original.raw[key]
    return enriched


def enrich_candidate_metadata(
    session: requests.Session,
    candidate: RepoCandidate,
    search_filter: GitHubSearchFilter,
    delay: float,
) -> RepoCandidate:
    if not metadata_filter_requested(search_filter):
        return candidate
    if has_required_metadata(candidate, search_filter):
        return candidate

    repo_meta = fetch_repository_metadata(session, candidate.full_name, delay)
    if repo_meta is None:
        return candidate

    enriched = repo_meta_to_candidate(repo_meta, candidate.source_filter)
    return preserve_code_search_match_metadata(candidate, enriched)


def search_url_for(search_filter: GitHubSearchFilter) -> str:
    if search_filter.search_type == GitHubSearchType.CODE:
        return CODE_SEARCH_URL
    return REPOSITORY_SEARCH_URL


def search_params(
    search_filter: GitHubSearchFilter,
    page: int,
    per_page: int,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "q": search_filter.query,
        "per_page": per_page,
        "page": page,
    }
    if search_filter.sort:
        params["sort"] = search_filter.sort
    if search_filter.order:
        params["order"] = search_filter.order
    return params


def candidate_from_search_item(
    item: dict[str, Any],
    search_filter: GitHubSearchFilter,
) -> RepoCandidate:
    if search_filter.search_type != GitHubSearchType.CODE:
        return repo_meta_to_candidate(item, search_filter.name)

    repo_meta = item.get("repository", {})
    candidate = repo_meta_to_candidate(repo_meta, search_filter.name)
    candidate.raw["_matched_path"] = item.get("path")
    candidate.raw["_matched_file_url"] = item.get("html_url")
    candidate.raw.setdefault(
        "_matches",
        [
            {
                "path": item.get("path"),
                "html_url": item.get("html_url"),
                "source_filter": search_filter.name,
            }
        ],
    )
    return candidate


def search_filter_candidates(
    session: requests.Session,
    search_filter: GitHubSearchFilter,
    max_items: int,
    delay: float,
) -> list[RepoCandidate]:
    url = search_url_for(search_filter)
    candidates: list[RepoCandidate] = []
    per_page = min(max(search_filter.per_page, 1), 100)
    page = 1

    log.info("[%s] query: %s", search_filter.search_type.value, search_filter.query)

    while len(candidates) < max_items:
        resp = safe_get(
            session,
            url,
            params=search_params(search_filter, page, per_page),
            delay=delay,
        )
        if resp is None:
            break

        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            candidate = candidate_from_search_item(item, search_filter)
            candidate = enrich_candidate_metadata(session, candidate, search_filter, delay)
            if is_usable_candidate(candidate) and candidate_matches_metadata_filter(candidate, search_filter):
                candidates.append(candidate)

            if len(candidates) >= max_items:
                break

        total = data.get("total_count", 0)
        log.info(
            "Pagina %s | itens: %s | candidatos acumulados: %s / %s",
            page,
            len(items),
            len(candidates),
            total,
        )

        if page * per_page >= min(total, GITHUB_SEARCH_RESULT_LIMIT):
            break

        page += 1
    return candidates


def search_filter_candidates_page(
    session: requests.Session,
    search_filter: GitHubSearchFilter,
    page: int,
    per_page: int,
    delay: float,
) -> tuple[list[RepoCandidate], int, bool]:
    url = search_url_for(search_filter)
    per_page = min(max(per_page, 1), 100)
    page = max(page, 1)

    log.info(
        "[%s] pagina %s | query: %s",
        search_filter.search_type.value,
        page,
        search_filter.query,
    )
    resp = safe_get(
        session,
        url,
        params=search_params(search_filter, page, per_page),
        delay=delay,
    )
    if resp is None:
        return [], 0, False

    data = resp.json()
    items = data.get("items", [])
    total = int(data.get("total_count", 0) or 0)
    candidates: list[RepoCandidate] = []

    for item in items:
        candidate = candidate_from_search_item(item, search_filter)
        candidate = enrich_candidate_metadata(session, candidate, search_filter, delay)
        if is_usable_candidate(candidate) and candidate_matches_metadata_filter(candidate, search_filter):
            candidates.append(candidate)

    has_next_page = bool(items) and page * per_page < min(total, GITHUB_SEARCH_RESULT_LIMIT)
    log.info(
        "Pagina %s | itens=%s | candidatos_utilizaveis=%s | total_api=%s | tem_proxima=%s",
        page,
        len(items),
        len(candidates),
        total,
        has_next_page,
    )
    return candidates, total, has_next_page


def fetch_mining_page(
    token: str,
    filters: list[GitHubSearchFilter],
    page: int,
    per_page: int,
    delay: float,
    seen_keys: set[str],
    session: requests.Session | None = None,
) -> MiningPage:
    session = session or build_session(token)
    candidates_by_key: dict[str, tuple[int, RepoCandidate, GitHubSearchFilter]] = {}
    total_count = 0
    has_next_page = False

    for search_filter in filters:
        candidates, filter_total, filter_has_next = search_filter_candidates_page(
            session=session,
            search_filter=search_filter,
            page=page,
            per_page=per_page,
            delay=delay,
        )
        total_count += filter_total
        has_next_page = has_next_page or filter_has_next

        for page_index, candidate in enumerate(candidates):
            key = candidate_key(candidate)
            if key in seen_keys:
                continue
            if key in candidates_by_key:
                merge_candidate_metadata(candidates_by_key[key][1], candidate)
                continue
            candidates_by_key[key] = (page_index, candidate, search_filter)

    return MiningPage(
        candidates=list(candidates_by_key.values()),
        total_count=total_count,
        has_next_page=has_next_page,
    )


def mine_candidates(
    token: str,
    page_candidates: list[tuple[int, RepoCandidate, GitHubSearchFilter]],
    max_workers: int,
    delay: float,
) -> list[tuple[int, str, MinedRepo]]:
    results: list[tuple[int, str, MinedRepo]] = []
    max_workers = max(max_workers, 1)
    batch_size = max_workers * 4

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for start in range(0, len(page_candidates), batch_size):
            batch = page_candidates[start : start + batch_size]
            futures = {
                executor.submit(
                    analyze_candidate_in_worker,
                    token,
                    candidate,
                    search_filter,
                    delay,
                ): (page_index, candidate_key(candidate))
                for page_index, candidate, search_filter in batch
            }

            for future in as_completed(futures):
                page_index, key = futures[future]
                try:
                    repo = future.result()
                except Exception as exc:
                    log.error("Erro ao minerar candidato da pagina: %s", exc)
                    continue

                if repo is not None:
                    results.append((page_index, key, repo))

    return results


def fetch_file_content(
    session: requests.Session,
    full_name: str,
    path: str,
    delay: float,
) -> str | None:
    encoded_path = quote(path.strip("/"), safe="/")
    url = CONTENTS_URL.format(full_name=full_name, path=encoded_path)
    resp = safe_get(session, url, delay=delay)
    if resp is None:
        return None

    data = resp.json()
    if not isinstance(data, dict):
        return None

    if data.get("encoding") != "base64" or not data.get("content"):
        return None

    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception as exc:
        log.debug("Falha ao decodificar %s/%s: %s", full_name, path, exc)
        return None


def fetch_directory_items(
    session: requests.Session,
    full_name: str,
    path: str,
    delay: float,
) -> list[dict[str, Any]]:
    encoded_path = quote(path.strip("/"), safe="/")
    url = CONTENTS_URL.format(full_name=full_name, path=encoded_path)
    resp = safe_get(session, url, delay=delay)
    if resp is None:
        return []

    data = resp.json()
    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def fetch_ref_commit_sha(
    session: requests.Session,
    full_name: str,
    ref: str,
    delay: float,
) -> str | None:
    url = COMMITS_URL.format(full_name=full_name, ref=quote(ref, safe=""))
    resp = safe_get(session, url, delay=delay)
    if resp is None:
        return None

    data = resp.json()
    if not isinstance(data, dict):
        return None

    sha = data.get("sha")
    return str(sha).strip() if sha else None


def regex_value(pattern: str, content: str) -> Any | None:
    match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    if match.groups():
        return match.group(1).strip()
    return True


def normalize_java_version(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None

    match = re.match(r"^(?:1\.)?(\d+)(?:\.\d+)*", text)
    if not match:
        return None

    return match.group(1)


def extract_java_version_from_pom(content: str) -> str | None:
    for pattern in JAVA_VERSION_PATTERNS:
        match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        if not match:
            continue

        return normalize_java_version(match.group(1))

    return None


def pom_indicates_spring(content: str) -> bool:
    return bool(
        re.search(
            r"<(?:groupId|artifactId)>\s*(?:org\.springframework|spring-[^<]+)",
            content,
            re.IGNORECASE,
        )
    )


def content_has_spring_import(content: str) -> bool:
    return bool(
        re.search(
            r"^\s*import\s+org\.springframework(?:\.|\s*;)",
            content,
            re.MULTILINE,
        )
    )


def find_spring_import_file(
    session: requests.Session,
    full_name: str,
    delay: float,
    root_path: str = MAIN_JAVA_PATH,
) -> str | None:
    pending = [root_path]
    checked_files = 0

    while pending and checked_files < MAX_MAIN_SOURCE_FILES_TO_CHECK:
        current_path = pending.pop(0)
        for item in fetch_directory_items(session, full_name, current_path, delay):
            item_type = str(item.get("type") or "")
            item_path = str(item.get("path") or "")
            if not item_path:
                continue

            if item_type == "dir":
                pending.append(item_path)
                continue

            if item_type != "file" or not item_path.endswith(".java"):
                continue

            checked_files += 1
            content = fetch_file_content(session, full_name, item_path, delay)
            if content and content_has_spring_import(content):
                return item_path

            if checked_files >= MAX_MAIN_SOURCE_FILES_TO_CHECK:
                break

    return None


def apply_content_rules(
    content: str,
    rules: list[ContentRule],
) -> tuple[bool, dict[str, Any]]:
    metadata: dict[str, Any] = {}

    for rule in rules:
        value: Any | None = None

        if not rule.patterns and rule.fixed_value is not None:
            value = rule.fixed_value
        else:
            for pattern in rule.patterns:
                found = regex_value(pattern, content)
                if found is not None:
                    value = rule.fixed_value if rule.fixed_value is not None else found
                    break

        if value is None:
            if rule.required:
                return False, {}
            continue

        metadata[rule.field_name] = value

    return True, metadata


def analyze_candidate(
    session: requests.Session,
    candidate: RepoCandidate,
    search_filter: GitHubSearchFilter,
    delay: float,
) -> MinedRepo | None:
    license_info = candidate.raw.get("license")
    license_key = None
    license_name = None
    if isinstance(license_info, dict):
        license_key = license_info.get("key")
        license_name = license_info.get("name")

    metadata: dict[str, Any] = {
        "description": candidate.description,
        "language": candidate.language,
        "stars": candidate.stars,
        "stargazers_count": candidate.stars,
        "forks": candidate.forks,
        "open_issues": candidate.open_issues,
        "topics": candidate.topics,
        "default_branch": candidate.raw.get("default_branch"),
        "license": license_key,
        "license_key": license_key,
        "license_name": license_name,
        "created_at": format_github_date_to_br(candidate.raw.get("created_at")),
        "updated_at": format_github_date_to_br(candidate.raw.get("updated_at")),
        "pushed_at": format_github_date_to_br(candidate.raw.get("pushed_at")),
        "last_push_at": format_github_date_to_br(candidate.raw.get("pushed_at")),
    }
    commit_sha = None
    content_path = (
        search_filter.file_path
        or candidate.raw.get("_matched_path")
    )
    pom_content = None

    if content_path:
        content = fetch_file_content(session, candidate.full_name, content_path, delay)
        if content is None:
            return None

        metadata["matched_file"] = content_path
        if content_path.lower().endswith("pom.xml"):
            pom_content = content
            java_version = extract_java_version_from_pom(content)
            if java_version:
                metadata["java_version"] = java_version

        ok, extracted = apply_content_rules(content, search_filter.content_rules)
        if not ok:
            return None
        metadata.update(extracted)
    elif search_filter.content_rules:
        return None

    if pom_content is None:
        pom_content = fetch_file_content(session, candidate.full_name, ROOT_POM_PATH, delay)
        if pom_content is None:
            return None

        java_version = extract_java_version_from_pom(pom_content)
        if java_version and "java_version" not in metadata:
            metadata["java_version"] = java_version

    default_branch = str(candidate.raw.get("default_branch") or "").strip()
    if default_branch:
        commit_sha = (
            candidate.raw.get("sha")
            or candidate.raw.get("commit_sha")
            or fetch_ref_commit_sha(
                session,
                candidate.full_name,
                default_branch,
                delay,
            )
        )
        if commit_sha:
            commit_sha = str(commit_sha).strip()
            metadata["commit_sha"] = commit_sha

    return mined_repo_from_candidate(candidate, metadata, commit_sha=commit_sha)


def analyze_candidate_in_worker(
    token: str,
    candidate: RepoCandidate,
    search_filter: GitHubSearchFilter,
    delay: float,
) -> MinedRepo | None:
    return analyze_candidate(
        worker_session(token),
        candidate,
        search_filter,
        delay,
    )


def run_mining(
    token: str,
    filters: list[GitHubSearchFilter],
    max_repos: int = 100,
    max_workers: int = 5,
    delay: float = 0.0,
    stop_when_limit_reached: bool = True,
    candidate_multiplier: int = 10,
) -> list[MinedRepo]:
    '''
    Busca candidatos no GitHub, Deduplica os candidatos por chave unica, 
    Analisa cada candidato em paralelo e retorna os repositorios minerados 
    que passaram nas regras de conteudo. Para quando atingir max_repos 
    repositorios minerados se stop_when_limit_reached for True.
    '''
    session = build_session(token)
    candidates_by_key: dict[str, tuple[RepoCandidate, GitHubSearchFilter]] = {}

    log.info(
        "Mineracao iniciada | filtros=%s | max_repos=%s | workers=%s | delay=%s",
        len(filters),
        max_repos,
        max_workers,
        delay,
    )

    for search_filter in filters:
        found = search_filter_candidates(
            session=session,
            search_filter=search_filter,
            max_items=max_repos * max(candidate_multiplier, 1),
            delay=delay,
        )
        for candidate in found:
            key = candidate_key(candidate)
            if key not in candidates_by_key:
                candidates_by_key[key] = (candidate, search_filter)

    log.info("Total de candidatos unicos: %s", len(candidates_by_key))

    results: list[MinedRepo] = []
    max_workers = max(max_workers, 1)
    batch_size = max_workers * 4

    log.info("Aplicando regras de conteudo em %s candidatos.", len(candidates_by_key))
    candidate_items = list(candidates_by_key.items())
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for start in range(0, len(candidate_items), batch_size):
            if stop_when_limit_reached and len(results) >= max_repos:
                break

            batch = candidate_items[start : start + batch_size]
            futures = {
                executor.submit(
                    analyze_candidate_in_worker,
                    token,
                    candidate,
                    search_filter,
                    delay,
                ): key
                for key, (candidate, search_filter) in batch
            }

            for future in as_completed(futures):
                if stop_when_limit_reached and len(results) >= max_repos:
                    break

                key = futures[future]
                try:
                    repo = future.result()
                except Exception as exc:
                    log.error("Erro ao analisar %s: %s", key, exc)
                    continue

                if repo is None:
                    continue

                results.append(repo)
                log.info(
                    "Repositorio aceito na mineracao %s/%s: %s",
                    len(results),
                    max_repos,
                    repo.repo_name,
                )

    log.info("Mineracao finalizada | repositorios selecionados=%s.", len(results))
    return results[:max_repos] if stop_when_limit_reached else results


def mined_repo_to_analyzer_entry(
    repo: MinedRepo,
    allow_jdk_upgrade: bool = False,
) -> dict[str, Any]:
    metadata = repo.metadata
    return {
        "repo_name": repo.repo_name,
        "repo_url": repo.repo_url,
        "java_version": str(metadata.get("java_version", "")),
        "allow_jdk_upgrade": allow_jdk_upgrade,
        "build": metadata.get("build", "Maven"),
        "test_framework": metadata.get("test_framework", ""),
        "commit_sha": repo.commit_sha or metadata.get("commit_sha"),
    }


def analysis_error_entry(entry: dict[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "name": entry.get("repo_name", ""),
        "repository_url": entry.get("repo_url", ""),
        "commit_sha": entry.get("commit_sha"),
        "java_version": entry.get("java_version", ""),
        "effective_java_version": entry.get("java_version", ""),
        "build": entry.get("build", "Maven"),
        "test_framework": entry.get("test_framework", ""),
        "compiled": False,
        "has_tests": False,
        "tests_passed": False,
        "eliminated": True,
        "error_stage": "unexpected",
        "error_message": str(exc),
    }


def cached_analysis_for_mined_repo(
    repo: MinedRepo,
    run_test_suite: bool,
    allow_jdk_upgrade: bool = False,
) -> dict[str, Any] | None:
    from app.services.persistence import get_analysis_cache, get_latest_analysis_cache

    commit_sha = str(repo.commit_sha or repo.metadata.get("commit_sha") or "").strip()
    cached_result = get_analysis_cache(
        repo.repo_name,
        commit_sha,
        run_test_suite,
        allow_jdk_upgrade,
    )
    cache_log_context = f"commit={commit_sha}" if commit_sha else "ultimo_resultado"
    if cached_result is None:
        cached_result = get_latest_analysis_cache(
            repo.repo_name,
            run_test_suite,
            allow_jdk_upgrade,
        )
        cache_log_context = "ultimo_resultado"
    if cached_result is None:
        return None

    cached_result["name"] = repo.repo_name
    cached_result["repository_url"] = repo.repo_url
    cached_result["repo_name"] = repo.repo_name
    cached_result["repo_url"] = repo.repo_url
    cached_result["matched_filter"] = repo.matched_filter
    cached_result["metadata"] = repo.metadata
    log.info("Cache hit do analyzer | %s | %s", repo.repo_name, cache_log_context)
    return cached_result


def analyze_mined_repositories(
    repositories: list[MinedRepo],
    max_workers: int = 4,
    run_test_suite: bool = True,
    allow_jdk_upgrade: bool = False,
) -> list[dict[str, Any]]:
    from app.services.analyzer import analyze_project, flush_completed_repos

    entries = [
        mined_repo_to_analyzer_entry(repo, allow_jdk_upgrade)
        for repo in repositories
    ]
    repository_by_url = {repo.repo_url: repo for repo in repositories}
    entry_by_url = {entry["repo_url"]: entry for entry in entries}
    results: list[dict[str, Any]] = []
    pending_entries: list[dict[str, Any]] = []
    cleanup_queue: list[str] = []
    max_workers = max(max_workers, 1)

    log.info("Iniciando analyzer para %s repositorios filtrados.", len(entries))

    for repo in repositories:
        cached_result = cached_analysis_for_mined_repo(
            repo,
            run_test_suite,
            allow_jdk_upgrade,
        )
        if cached_result is None:
            pending_entries.append(entry_by_url[repo.repo_url])
            continue

        results.append(cached_result)

    if not pending_entries:
        log.info("Analyzer finalizado usando somente cache | resultados=%s.", len(results))
        return results

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyze_project, entry, run_test_suite): entry
                for entry in pending_entries
            }

            for future in as_completed(futures):
                entry = futures[future]
                repo_name = str(entry.get("repo_name") or "").strip()
                try:
                    result = asdict(future.result())
                    source_repo = repository_by_url.get(result.get("repository_url", ""))
                    if source_repo is not None:
                        result["repo_name"] = source_repo.repo_name
                        result["repo_url"] = source_repo.repo_url
                        result["matched_filter"] = source_repo.matched_filter
                        result["metadata"] = source_repo.metadata
                    results.append(result)
                    cleanup_queue.append(str(result.get("name") or repo_name))
                    log.info(
                        "Analyzer progresso %s/%s | %s | compiled=%s | tests=%s | eliminated=%s",
                        len(results),
                        len(entries),
                        result.get("name") or result.get("repo_name"),
                        result.get("compiled"),
                        result.get("tests_passed"),
                        result.get("eliminated"),
                    )
                except Exception as exc:
                    log.error("Erro no analyzer para %s: %s", repo_name, exc)
                    results.append(analysis_error_entry(entry, exc))
                    cleanup_queue.append(repo_name)
    finally:
        if cleanup_queue:
            log.info("[cleanup] Limpando %s repositorios analisados pelo endpoint.", len(cleanup_queue))
            flush_completed_repos(cleanup_queue)

    log.info("Analyzer finalizado | resultados=%s.", len(results))
    return results
