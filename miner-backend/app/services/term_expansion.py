"""Expansão de um termo digitado pelo usuário em várias buscas do GitHub.

O usuário informa só o termo (ex.: "JDBC Template"). Daqui saem consultas
complementares, cada uma com a sua evidência de uso:

- ``codigo``: o nome da classe ou API em arquivos .java;
- ``import``: o import completo da classe em arquivos .java;
- ``dependencia``: o artifactId declarado em pom.xml.

O resultado é a união das consultas. Nada é baixado nem executado aqui.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from app.services import maven_discovery

CATALOG_PATH = Path(__file__).parent / "data" / "term_catalog.json"

# A busca de código do GitHub devolve no máximo 1000 resultados por consulta.
# Fatiar por tamanho de arquivo (bytes) dá a cada fatia a sua própria cota.
SIZE_SLICES: tuple[str, ...] = ("<1500", "1500..4000", "4000..10000", "10000..30000", ">30000")

MAX_TERM_LENGTH = 80


@dataclass(frozen=True)
class TermQuery:
    query: str  # texto da busca, entre aspas
    evidence: str  # codigo | import | import_prefix | dependencia
    text: str = ""  # o mesmo texto sem aspas, usado na triagem do arquivo
    filename: str | None = None
    extension: str | None = None
    file_size: str | None = None
    note: str = ""


@dataclass(frozen=True)
class TermExpansion:
    term: str
    from_catalog: bool
    queries: list[TermQuery]
    # De onde vieram as buscas: catalogo | maven_central | cache | sem_resultado | indisponivel | desligado
    source: str = "catalogo"
    artifacts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "from_catalog": self.from_catalog,
            "source": self.source,
            "artifacts": self.artifacts,
            "queries": [asdict(query) for query in self.queries],
        }


def _ascii_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def normalize_term(term: str) -> str:
    """'  JDBC   Template ' -> 'jdbc template'."""
    return re.sub(r"\s+", " ", _ascii_lower(term)).strip()


def _words(term: str) -> list[str]:
    # Separa camelCase e separadores: "JdbcTemplate" e "jdbc-template" dão as mesmas palavras.
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", term.strip())
    return [word for word in re.split(r"[^A-Za-z0-9]+", _ascii_lower(spaced)) if word]


def validate_term(term: str) -> str:
    cleaned = re.sub(r"\s+", " ", term).strip()
    if not cleaned:
        raise ValueError("Informe um termo.")
    if len(cleaned) > MAX_TERM_LENGTH:
        raise ValueError(f"O termo deve ter no máximo {MAX_TERM_LENGTH} caracteres.")
    # O termo vira texto dentro de uma busca: bloqueia qualificadores e operadores.
    if re.search(r"[\"':()\\]", cleaned) or re.search(r"\b(AND|OR|NOT)\b", cleaned):
        raise ValueError("Use apenas o nome do termo, sem aspas, dois-pontos, parênteses ou operadores.")
    return cleaned


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict]:
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def find_catalog_entry(term: str) -> dict | None:
    key = normalize_term(term)
    compact = key.replace(" ", "")
    for name, entry in load_catalog().items():
        names = {name, *entry.get("aliases", [])}
        normalized = {normalize_term(item) for item in names}
        if key in normalized or compact in {item.replace(" ", "") for item in normalized}:
            return entry
    return None


def _camel(words: list[str]) -> str:
    return "".join(word.capitalize() for word in words)


def _phrase(text: str) -> str:
    return f'"{text}"'


def _unique(items: list[str]) -> list[str]:
    # A busca do GitHub não diferencia maiúsculas: JdbcTemplate e jdbctemplate são a mesma consulta.
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _generic_entry(term: str) -> dict:
    words = _words(term)
    camel = _camel(words)
    kebab = "-".join(words)
    typed = re.sub(r"\s+", " ", term).strip()
    return {
        "classes": _unique([typed, camel] if len(words) > 1 else [typed]),
        "imports": [],
        "dependencies": [kebab] if kebab else [],
    }


def expand_term(term: str, *, coverage: str = "ampla") -> TermExpansion:
    """Gera as consultas de código para o termo.

    ``coverage="rapida"`` gera uma consulta por evidência. ``"ampla"`` repete cada
    consulta de código por faixa de tamanho de arquivo, para passar do limite de
    1000 resultados por consulta.
    """
    if coverage not in {"rapida", "ampla"}:
        raise ValueError("coverage deve ser 'rapida' ou 'ampla'.")
    clean = validate_term(term)
    entry = find_catalog_entry(clean)
    from_catalog = entry is not None
    source = "catalogo"
    artifacts: list[dict] = []
    if entry is None:
        entry = _generic_entry(clean)
        # Termo fora do catálogo: procura no Maven Central as bibliotecas que combinam com ele.
        discovery = maven_discovery.discover(clean)
        source = discovery.source
        artifacts = [asdict(item) for item in discovery.artifacts]
        entry["dependencies"] = _unique([
            *entry.get("dependencies", []), *(item.artifact for item in discovery.artifacts)
        ])
        entry["import_prefixes"] = maven_discovery.groups_matching_term(clean, discovery.artifacts)

    base: list[TermQuery] = []
    for name in _unique(entry.get("classes", [])):
        base.append(TermQuery(_phrase(name), "codigo", name, extension="java", note=f"Uso de {name} no código"))
    for imported in _unique(entry.get("imports", [])):
        base.append(TermQuery(_phrase(imported), "import", imported, extension="java", note=f"Import {imported}"))
    for group in _unique(entry.get("import_prefixes", [])):
        base.append(TermQuery(_phrase(group), "import_prefix", group, extension="java", note=f"Import do grupo {group}"))
    for artifact in _unique(entry.get("dependencies", [])):
        base.append(TermQuery(_phrase(artifact), "dependencia", artifact, filename="pom.xml", note=f"Dependência {artifact} no pom.xml"))

    if coverage == "rapida":
        return TermExpansion(clean, from_catalog, base, source, artifacts)

    queries: list[TermQuery] = []
    for query in base:
        if query.evidence == "dependencia":
            # pom.xml é pequeno e raro por repositório; fatiar só gastaria cota de requisições.
            queries.append(query)
            continue
        # A consulta sem fatia vem primeiro: se ela couber no limite de 1000
        # resultados, as fatias seguintes sao puladas na hora da busca.
        queries.append(query)
        for size in SIZE_SLICES:
            queries.append(TermQuery(
                query.query, query.evidence, query.text, query.filename, query.extension, size,
                f"{query.note} (arquivos {size} bytes)",
            ))
    return TermExpansion(clean, from_catalog, queries, source, artifacts)
