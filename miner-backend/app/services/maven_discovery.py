"""Descobre, no Maven Central, as bibliotecas que correspondem a um termo fora do catálogo.

Para um termo como "Acme Widget" o Miner monta nomes prováveis de artifactId
(acme-widget, acme-widget-core, spring-acme-widget...), consulta o Maven Central e fica
com os que existem e são populares (mais versões publicadas). Cada artefato vira uma busca
de dependência no pom.xml e, quando o groupId combina com o termo, uma busca por import.

Se a internet ou o Maven Central falharem, nada quebra: a busca segue só com as variações
do nome do termo.

MINER_MAVEN_DISCOVERY=off desliga a consulta (os testes usam isso).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger("maven_discovery")

SEARCH_URL = "https://search.maven.org/solrsearch/select"
REQUEST_TIMEOUT = 8
ROWS = 30
MIN_VERSIONS = 3  # ignora artefatos quase sem histórico (ruído)
MAX_ARTIFACTS = 4
MAX_GROUPS = 2
CACHE_TTL_FOUND = 30 * 24 * 3600
CACHE_TTL_EMPTY = 24 * 3600

_cache_lock = threading.Lock()


@dataclass(frozen=True)
class Artifact:
    group: str
    artifact: str
    versions: int


@dataclass(frozen=True)
class Discovery:
    source: str  # maven_central | cache | sem_resultado | indisponivel | desligado
    artifacts: list[Artifact]

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "artifacts": [asdict(item) for item in self.artifacts]}


def enabled() -> bool:
    return os.environ.get("MINER_MAVEN_DISCOVERY", "on").strip().lower() != "off"


def term_words(term: str) -> list[str]:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", term.strip())
    return [word for word in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if word]


def candidate_artifact_ids(term: str) -> list[str]:
    words = term_words(term)
    if not words:
        return []
    kebab = "-".join(words)
    compact = "".join(words)
    ids = [
        kebab, f"{kebab}-core", f"{kebab}-api", f"spring-{kebab}",
        f"{kebab}-starter", f"spring-boot-starter-{kebab}", f"{kebab}-spring-boot-starter",
        compact, f"{compact}-core",
    ]
    seen: set[str] = set()
    return [item for item in ids if not (item in seen or seen.add(item))]


def _solr_query(ids: list[str]) -> str:
    return " OR ".join(f'a:"{item}"' for item in ids)


def groups_matching_term(term: str, artifacts: list[Artifact]) -> list[str]:
    """groupIds que servem de prefixo de import: só os que contêm uma palavra do termo.

    Isso evita prefixos genéricos (org.apache, com.google) que casariam com qualquer projeto.
    """
    words = [word for word in term_words(term) if len(word) >= 4]
    groups: list[str] = []
    for item in artifacts:
        if item.group in groups or item.group.count(".") < 1:
            continue
        if any(word in item.group.lower() for word in words):
            groups.append(item.group)
    return groups[:MAX_GROUPS]


# --- cache em arquivo (no volume de dados); qualquer falha de leitura/escrita é ignorada -----

def _cache_path() -> Path | None:
    configured = os.environ.get("MINER_MAVEN_CACHE", "").strip()
    if configured:
        return Path(configured)
    try:
        from app.core import database

        return Path(database.DATABASE_PATH).parent / "maven_discovery_cache.json"
    except Exception:  # noqa: BLE001
        return None


def _cache_read(key: str) -> list[Artifact] | None:
    path = _cache_path()
    if path is None:
        return None
    try:
        with _cache_lock, path.open(encoding="utf-8") as handle:
            entry = json.load(handle).get(key)
        if not entry:
            return None
        ttl = CACHE_TTL_FOUND if entry["artifacts"] else CACHE_TTL_EMPTY
        if time.time() - float(entry["at"]) > ttl:
            return None
        return [Artifact(**item) for item in entry["artifacts"]]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _cache_write(key: str, artifacts: list[Artifact]) -> None:
    path = _cache_path()
    if path is None:
        return
    try:
        with _cache_lock:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            data[key] = {"at": time.time(), "artifacts": [asdict(item) for item in artifacts]}
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
    except OSError as exc:
        log.debug("Cache do Maven Central não gravado: %s", exc)


def _fetch(ids: list[str]) -> list[dict[str, Any]] | None:
    params = {"q": _solr_query(ids), "rows": ROWS, "wt": "json"}
    for attempt in (1, 2):  # o Maven Central às vezes responde erro passageiro
        try:
            response = requests.get(SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                docs = response.json().get("response", {}).get("docs", [])
                return [doc for doc in docs if isinstance(doc, dict)]
            log.info("Maven Central respondeu %s (tentativa %s).", response.status_code, attempt)
        except (requests.RequestException, ValueError) as exc:
            log.info("Maven Central indisponível (tentativa %s): %s", attempt, exc)
        time.sleep(0.5)
    return None


def discover(term: str) -> Discovery:
    if not enabled():
        return Discovery("desligado", [])
    ids = candidate_artifact_ids(term)
    if not ids:
        return Discovery("sem_resultado", [])

    key = "|".join(term_words(term))
    cached = _cache_read(key)
    if cached is not None:
        return Discovery("cache" if cached else "sem_resultado", cached)

    docs = _fetch(ids)
    if docs is None:
        return Discovery("indisponivel", [])

    found: dict[tuple[str, str], int] = {}
    for doc in docs:
        group, artifact = doc.get("g"), doc.get("a")
        if not isinstance(group, str) or not isinstance(artifact, str) or artifact not in ids:
            continue
        versions = doc.get("versionCount")
        found[(group, artifact)] = int(versions) if isinstance(versions, int) else 0

    ranked = sorted(
        (Artifact(group, artifact, versions) for (group, artifact), versions in found.items()
         if versions >= MIN_VERSIONS),
        key=lambda item: (-item.versions, item.artifact),
    )[:MAX_ARTIFACTS]
    _cache_write(key, ranked)
    return Discovery("maven_central" if ranked else "sem_resultado", ranked)
