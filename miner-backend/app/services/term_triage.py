"""Triagem do termo: confirma, só pela API, que o arquivo que casou usa mesmo o termo.

A busca de código do GitHub acha o texto em qualquer lugar do arquivo: comentário,
texto entre aspas ou uma dependência só declarada para exclusão. Aqui o conteúdo do
arquivo é lido e esses casos são descartados, antes de qualquer clone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TriageResult:
    confirmed: bool
    reason: str


_NON_NEWLINE = re.compile(r"[^\n]")


def _blank(text: str) -> str:
    return _NON_NEWLINE.sub(" ", text)


def strip_java_noise(source: str) -> str:
    """Troca comentários e o conteúdo de strings por espaços, mantendo as quebras de linha."""
    out: list[str] = []
    i, n = 0, len(source)
    while i < n:
        char = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if char == "/" and nxt == "/":
            end = source.find("\n", i)
            end = n if end == -1 else end
            out.append(" " * (end - i))
            i = end
        elif char == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append(_blank(source[i:end]))
            i = end
        elif source.startswith('"""', i):
            end = source.find('"""', i + 3)
            end = n if end == -1 else end + 3
            out.append(_blank(source[i:end]))
            i = end
        elif char in "\"'":
            end = i + 1
            while end < n and source[end] != char and source[end] != "\n":
                end += 2 if source[end] == "\\" else 1
            end = min(end + 1, n)
            out.append(" " * (end - i))
            i = end
        else:
            out.append(char)
            i += 1
    return "".join(out)


def _word_pattern(text: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w.]){re.escape(text)}(?![\w])", re.IGNORECASE)


def _confirm_code(text: str, content: str) -> TriageResult:
    code = strip_java_noise(content)
    if re.search(rf"(?<![\w]){re.escape(text)}(?![\w])", code, re.IGNORECASE):
        return TriageResult(True, "uso_no_codigo")
    if text.lower() in content.lower():
        return TriageResult(False, "apenas_comentario_ou_texto")
    return TriageResult(False, "termo_ausente_no_arquivo")


def _confirm_import(text: str, content: str) -> TriageResult:
    code = strip_java_noise(content)
    if _word_pattern(text).search(code):
        return TriageResult(True, "import")
    package, _, simple = text.rpartition(".")
    if package and re.search(rf"\bimport\s+{re.escape(package)}\.\*\s*;", code):
        if re.search(rf"\b{re.escape(simple)}\b", code):
            return TriageResult(True, "import_com_curinga")
    if text.lower() in content.lower():
        return TriageResult(False, "apenas_comentario_ou_texto")
    return TriageResult(False, "termo_ausente_no_arquivo")


def _confirm_import_prefix(text: str, content: str) -> TriageResult:
    """O groupId serve de prefixo do pacote: basta um import dentro dele."""
    code = strip_java_noise(content)
    if re.search(rf"\bimport\s+(?:static\s+)?{re.escape(text)}\.", code):
        return TriageResult(True, "import_do_grupo")
    if text.lower() in content.lower():
        return TriageResult(False, "apenas_comentario_ou_texto")
    return TriageResult(False, "termo_ausente_no_arquivo")


_XML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_DEPENDENCY_MANAGEMENT = re.compile(r"<dependencyManagement>.*?</dependencyManagement>", re.DOTALL)
_EXCLUSIONS = re.compile(r"<exclusions>.*?</exclusions>", re.DOTALL)
_DEPENDENCY_BLOCK = re.compile(r"<dependency>(.*?)</dependency>", re.DOTALL)


def _confirm_dependency(text: str, content: str) -> TriageResult:
    cleaned = _XML_COMMENT.sub("", content)
    # dependencyManagement só fixa versão; exclusions remove a dependência. Nenhum dos dois é uso.
    cleaned = _DEPENDENCY_MANAGEMENT.sub("", cleaned)
    cleaned = _EXCLUSIONS.sub("", cleaned)
    artifact = re.compile(rf"<artifactId>\s*{re.escape(text)}\s*</artifactId>", re.IGNORECASE)
    for block in _DEPENDENCY_BLOCK.findall(cleaned):
        if artifact.search(block):
            return TriageResult(True, "dependencia")
    if text.lower() in content.lower():
        return TriageResult(False, "dependencia_nao_efetiva")
    return TriageResult(False, "termo_ausente_no_arquivo")


def confirm_evidence(kind: str, text: str, content: str) -> TriageResult:
    if kind == "codigo":
        return _confirm_code(text, content)
    if kind == "import":
        return _confirm_import(text, content)
    if kind == "import_prefix":
        return _confirm_import_prefix(text, content)
    if kind == "dependencia":
        return _confirm_dependency(text, content)
    return TriageResult(True, "sem_triagem")
