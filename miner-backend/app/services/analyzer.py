from __future__ import annotations

from collections import deque
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.services.persistence_policy import filter_persistable_repositories

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Diretórios e constantes
# ---------------------------------------------------------------------------

BASE_DIR    = Path(__file__).parent
REPOS_DIR   = BASE_DIR / "repos"
LOGS_DIR    = BASE_DIR / "logs"
INPUT_JSON  = BASE_DIR / "repositories.json"
OUTPUT_JSON = BASE_DIR / "output.json"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
REPOS_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT_CLONE   = 300
TIMEOUT_COMPILE = 300
TIMEOUT_TEST    = 600
TIMEOUT_REPOSITORY = 900
PROCESS_LOG_LIMIT = 32 * 1024
MAX_WORKERS     = 4
MAX_RETRIES     = 3
RETRY_BACKOFF   = 5
CLEANUP_BATCH_SIZE = 5
SAVE_BATCH_SIZE = 5   # grava output.json a cada N projetos concluídos (em vez de a cada 1)
PERSIST_ELIMINATED_REPOSITORIES = (
    os.environ.get("PERSIST_ELIMINATED_REPOSITORIES", "")
    .strip()
    .lower()
    in {"1", "true", "sim", "yes", "y"}
)

# ---------------------------------------------------------------------------
# Mapeamento completo de JDKs (sdkman)
# ---------------------------------------------------------------------------

JDK_BASE_DIR = Path(
    os.environ.get(
        "JDK_BASE_DIR",
        os.environ.get("SDKMAN_JAVA_DIR", "/home/laris/.sdkman/candidates/java"),
    )
)

JDK_MAP: dict[str, Path] = {
    "1.6": JDK_BASE_DIR / "6.0.119-zulu",
    "1.7": JDK_BASE_DIR / "7.0.352-zulu",
    "1.8": JDK_BASE_DIR / "8.0.402-zulu",
    "6":   JDK_BASE_DIR / "6.0.119-zulu",
    "7":   JDK_BASE_DIR / "7.0.352-zulu",
    "8":   JDK_BASE_DIR / "8.0.402-zulu",
    "11":  JDK_BASE_DIR / "11.0.22-tem",
    "14":  JDK_BASE_DIR / "14.0.2-open",
    "15":  JDK_BASE_DIR / "15.0.2-open",
    "16":  JDK_BASE_DIR / "16.0.2-open",
    "17":  JDK_BASE_DIR / "17.0.10-tem",
    "18":  JDK_BASE_DIR / "18.0.2-open",
    "19":  JDK_BASE_DIR / "19.0.2-open",
    "20":  JDK_BASE_DIR / "20.0.2-open",
    "21":  JDK_BASE_DIR / "21.0.2-tem",
    "22":  JDK_BASE_DIR / "22.0.2-zulu",
    "23":  JDK_BASE_DIR / "23.0.2-zulu",
    "25":  JDK_BASE_DIR / "25-open",
}

VERSIONS_ASC  = ["6","7","8","11","14","15","16","17","18","19","20","21","22","23","25"]
MAVEN_MIN_VER = "8"   # Maven precisa de Java ≥ 8 para iniciar

# class file major version → Java version
CLASS_VER_MAP: dict[int, str] = {
    50:"6", 51:"7", 52:"8", 53:"9", 54:"10",
    55:"11", 56:"12", 57:"13", 58:"14", 59:"15",
    60:"16", 61:"17", 62:"18", 63:"19", 64:"20",
    65:"21", 66:"22", 67:"23", 68:"24", 69:"25",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    log_file = LOGS_DIR / f"analyzer_{time.strftime('%Y%m%d_%H%M%S')}.log"
    fmt = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    logging.basicConfig(
        level=logging.DEBUG, format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return logging.getLogger("analyzer")


log = setup_logging()

# ---------------------------------------------------------------------------
# Estrutura de resultado
# ---------------------------------------------------------------------------

@dataclass
class ProjectResult:
    name: str
    repository_url: str
    java_version: str            # versão declarada no JSON
    effective_java_version: str  # versão realmente usada, igual à selecionada/detectada
    build: str
    test_framework: str
    commit_sha: str | None = None
    compiled: bool = False
    has_tests: bool = False
    tests_passed: bool = False
    eliminated: bool = False
    error_stage: str | None = None
    error_message: str | None = None

    def mark_eliminated(self, stage: str, message: str) -> None:
        self.eliminated    = True
        self.error_stage   = stage
        self.error_message = message[:1000]


@dataclass
class ProjectScan:
    root_pom: Path | None = None
    has_tests: bool = False

FRAMEWORK_PATTERNS: dict[str, list[str]] = {
    "Mockito": [
        r"<artifactId>\s*mockito-core\s*</artifactId>",
        r"<artifactId>\s*mockito-all\s*</artifactId>",
        r"<artifactId>\s*mockito-junit-jupiter\s*</artifactId>",
        r"<groupId>\s*org\.mockito\s*</groupId>",
    ],
    "TestNG": [
        r"<artifactId>\s*testng\s*</artifactId>",
        r"<groupId>\s*org\.testng\s*</groupId>",
    ],
    "JUnit": [
        r"<artifactId>\s*junit\s*</artifactId>",
        r"<artifactId>\s*junit-jupiter(?:-[^<]+)?\s*</artifactId>",
        r"<artifactId>\s*junit-vintage(?:-[^<]+)?\s*</artifactId>",
        r"<groupId>\s*org\.junit(?:\.jupiter)?\s*</groupId>",
    ],
}

# ---------------------------------------------------------------------------
# Resolução e upgrade opcional de JDK
# ---------------------------------------------------------------------------

def normalize_version(raw: str) -> str:
    """'1.8.0_202' → '1.8' | '22.0.1' → '22' | '11' → '11'."""
    raw = raw.strip()
    if re.match(r"^1\.\d+", raw):
        m = re.match(r"^(1\.\d+)", raw)
        return m.group(1) if m else raw
    m = re.match(r"^(\d+)", raw)
    return m.group(1) if m else raw


def canonical(ver: str) -> str:
    """'1.8' → '8', '1.6' → '6', '11' → '11'."""
    if ver.startswith("1."):
        return ver.split(".")[1]
    return ver


def jdk_path_for(ver_key: str) -> Path | None:
    path = JDK_MAP.get(ver_key)
    if path and path.exists():
        return path
    c = canonical(ver_key)
    path = JDK_MAP.get(c)
    if path and path.exists():
        return path

    java_home = os.environ.get("JAVA_HOME")
    java_home_version = os.environ.get("JAVA_HOME_VERSION")
    if java_home and java_home_version and c == canonical(normalize_version(java_home_version)):
        java_home_path = Path(java_home)
        if java_home_path.exists():
            return java_home_path

    return None


def upgrade_jdk(minimum: str) -> tuple[Path | None, str]:
    """Menor JDK disponível com versão >= minimum."""
    min_c = canonical(normalize_version(minimum))
    for v in VERSIONS_ASC:
        if int(v) >= int(min_c):
            p = jdk_path_for(v)
            if p:
                return p, v
    return None, minimum


def resolve_jdk(declared: str, allow_jdk_upgrade: bool = False) -> tuple[Path | None, str]:
    """
    Resolve o JDK da versão declarada/selecionada.
    Quando allow_jdk_upgrade=True, usa o menor JDK superior disponível se
    Maven ou a disponibilidade local exigirem.
    """
    key  = normalize_version(declared)
    c = canonical(key)
    if not c.isdigit():
        return None, key

    path = jdk_path_for(key)
    if path:
        if allow_jdk_upgrade and int(c) < int(MAVEN_MIN_VER):
            up_path, up_ver = upgrade_jdk(MAVEN_MIN_VER)
            if up_path:
                log.info(
                    "Java %s < 8: Maven não pode iniciar. Usando JDK %s.",
                    c,
                    up_ver,
                )
                return up_path, up_ver
        return path, canonical(key)

    if allow_jdk_upgrade:
        up_path, up_ver = upgrade_jdk(c)
        if up_path:
            log.warning("JDK %s não encontrado; usando %s como substituto.", key, up_ver)
            return up_path, up_ver

    return None, key


def build_env(jdk_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["JAVA_HOME"] = str(jdk_path)
    env["PATH"]      = str(jdk_path / "bin") + ":" + env.get("PATH", "")
    return env

# ---------------------------------------------------------------------------
# Leitura do pom.xml
# ---------------------------------------------------------------------------

def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def read_pom_required_version(pom_path: Path) -> str | None:
    """Retorna a versão Java exigida pelo pom.xml (source/target/release) ou None."""
    try:
        root = ET.parse(pom_path).getroot()
    except ET.ParseError:
        return None

    prop_tags = {"maven.compiler.release", "maven.compiler.source",
                 "maven.compiler.target", "java.version", "jdk.version"}
    for elem in root.iter():
        tag = _strip_ns(elem.tag)
        if tag in prop_tags and elem.text:
            c = canonical(normalize_version(elem.text.strip()))
            if re.match(r"^\d+$", c):
                return c

    for plugin in root.iter():
        if _strip_ns(plugin.tag) != "plugin":
            continue
        artifact = ""
        for child in plugin:
            if _strip_ns(child.tag) == "artifactId":
                artifact = (child.text or "").strip()
        if artifact != "maven-compiler-plugin":
            continue
        for cfg in plugin.iter():
            if _strip_ns(cfg.tag) in ("source", "target", "release") and cfg.text:
                c = canonical(normalize_version(cfg.text.strip()))
                if re.match(r"^\d+$", c):
                    return c
    return None


def detect_test_framework_from_pom(pom_path: Path) -> str:
    try:
        content = pom_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""

    detected = [
        framework
        for framework, patterns in FRAMEWORK_PATTERNS.items()
        if any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)
    ]

    return ", ".join(detected)

# ---------------------------------------------------------------------------
# Diagnóstico de erros de compilação / teste
# ---------------------------------------------------------------------------

def detect_required_version_from_error(output: str) -> str | None:
    """
    Extrai a versão mínima de Java necessária a partir da saída de erro.

    P2: invalid target release: X  /  release version X not supported
    P3a: class file has wrong version X.0, should be Y.0
    P3b: compiled by a more recent version of the Java Runtime (class file version X.0)
    """
    # P2
    m = re.search(r"(?:invalid target release|release version)[:\s]+(\d+)", output)
    if m:
        return m.group(1)

    # P3a — "class file has wrong version 61.0"
    m = re.search(r"class file has wrong version (\d+)\.0", output)
    if m:
        return CLASS_VER_MAP.get(int(m.group(1)))

    # P3b — "compiled by a more recent version … (class file version 65.0)"
    m = re.search(r"class file version (\d+)\.0\)", output)
    if m:
        return CLASS_VER_MAP.get(int(m.group(1)))

    return None


def is_source_target_error(output: str) -> bool:
    """
    P4: código usa sintaxe Java 8+ (lambdas, diamond, streams) mas recebeu
    -source mais antigo via flags explícitas de compilação.
    """
    patterns = [
        r"lambda expressions are not supported in -source",
        r"diamond operator is not supported in -source",
        r"multi-catch statement is not supported in -source",
        r"strings in switch are not supported in -source",
        r"try-with-resources is not supported in -source",
        r"not supported in -source 1\.[5678]",
        r"use -source [89]",
    ]
    return any(re.search(p, output) for p in patterns)


def is_missing_submodule_error(output: str) -> bool:
    """P5: clone raso não baixou submódulos declarados no pom.xml."""
    return bool(re.search(r"Child module .+ does not exist", output))


def classify_test_failure(output: str) -> str:
    """
    Diferencia falhas de teste por infraestrutura (Selenium/Appium sem driver/browser)
    de falhas genuínas de código.
    Retorna "tests_infra" ou "tests".
    """
    infra_patterns = [
        r"Tests run: 0.*BUILD FAILURE",
        r"Cannot instantiate.*[Dd]river",
        r"WebDriver.*null",
        r"driver.*null.*quit\(\)",
        r"SessionNotCreatedException",
        r"WebDriverException",
        r"org\.openqa\.selenium\.WebDriverException",
        r"io\.appium\.java_client",
        r"AppiumDriver",
        r"ChromeDriver",
        r"FirefoxDriver",
        r"geckodriver",
        r"chromedriver",
    ]
    # Comprime espaços e quebras de linha para facilitar regex multiline
    flat = " ".join(output.split())
    for p in infra_patterns:
        if re.search(p, flat, re.IGNORECASE):
            return "tests_infra"
    return "tests"

# ---------------------------------------------------------------------------
# Subprocess
# ---------------------------------------------------------------------------

def remaining_timeout(deadline: float | None, timeout: int) -> int:
    if deadline is None:
        return timeout
    remaining = int(deadline - time.monotonic())
    return max(min(timeout, remaining), 1)


def run(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    deadline: float | None = None,
) -> tuple[bool, str]:
    effective_timeout = remaining_timeout(deadline, timeout)
    output_tail: deque[str] = deque()
    output_size = 0
    output_lock = threading.Lock()

    def append_output(text: str) -> None:
        nonlocal output_size
        with output_lock:
            output_tail.append(text)
            output_size += len(text.encode("utf-8", errors="ignore"))
            while output_size > PROCESS_LOG_LIMIT and output_tail:
                removed = output_tail.popleft()
                output_size -= len(removed.encode("utf-8", errors="ignore"))

    def output_text() -> str:
        with output_lock:
            return "".join(output_tail)

    try:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        started_at = time.monotonic()
        assert proc.stdout is not None

        def read_output() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                append_output(line)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()

        while proc.poll() is None:
            if time.monotonic() - started_at > effective_timeout:
                proc.kill()
                append_output(f"\nTimeout apos {effective_timeout}s\n")
                reader.join(timeout=1)
                return False, output_text()
            time.sleep(0.2)

        reader.join(timeout=1)
        return proc.returncode == 0, output_text()
    except subprocess.TimeoutExpired:
        return False, f"Timeout apos {effective_timeout}s"
    except FileNotFoundError as exc:
        return False, f"Comando não encontrado: {exc}"
    except OSError as exc:
        return False, f"Erro ao iniciar processo: {exc}"

# ---------------------------------------------------------------------------
# Clone / atualização
# ---------------------------------------------------------------------------

def clone_or_update(
    repo_url: str,
    target_dir: Path,
    shallow: bool = True,
    with_submodules: bool = False,
    expected_commit_sha: str | None = None,
    deadline: float | None = None,
) -> tuple[bool, str]:
    if target_dir.exists():
        if expected_commit_sha:
            current = current_commit_sha(target_dir)
            if current == expected_commit_sha:
                log.debug("Repo local ja esta no commit desejado: %s", target_dir.name)
                return True, "existente-no-commit"

        log.debug("Repo já existe; tentando git pull: %s", target_dir.name)
        ok, out = run(
            ["git", "pull", "--ff-only"],
            target_dir,
            os.environ.copy(),
            TIMEOUT_CLONE,
            deadline,
        )
        if not ok:
            log.warning("git pull falhou em %s — usando versão local.", target_dir.name)
        return True, "existente"

    depth_flags = ["--depth=1", "--single-branch"] if shallow else []
    submodule_flags = ["--recurse-submodules"] if with_submodules else []
    cmd = ["git", "clone"] + submodule_flags + depth_flags + [repo_url, str(target_dir)]
    log.info("Clonando%s %s -> %s", " (raso)" if shallow else " (completo)", repo_url, target_dir.name)
    return run(cmd, REPOS_DIR, os.environ.copy(), TIMEOUT_CLONE, deadline)


def clone_with_retry(
    repo_url: str,
    target_dir: Path,
    shallow: bool = True,
    with_submodules: bool = False,
    expected_commit_sha: str | None = None,
    deadline: float | None = None,
) -> tuple[bool, str]:
    last_out = ""
    for attempt in range(1, MAX_RETRIES + 1):
        ok, last_out = clone_or_update(
            repo_url,
            target_dir,
            shallow=shallow,
            with_submodules=with_submodules,
            expected_commit_sha=expected_commit_sha,
            deadline=deadline,
        )
        if ok:
            return True, last_out
        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF * (2 ** (attempt - 1))
            log.warning("Clone tentativa %d/%d falhou; aguardando %ds...", attempt, MAX_RETRIES, wait)
            time.sleep(wait)
    return False, last_out


def current_commit_sha(project_dir: Path) -> str | None:
    ok, out = run(
        ["git", "rev-parse", "HEAD"],
        project_dir,
        os.environ.copy(),
        30,
    )
    if not ok:
        return None
    return out.strip().splitlines()[-1] if out.strip() else None

# ---------------------------------------------------------------------------
# Detecção de testes
# ---------------------------------------------------------------------------

def scan_project_structure(project_dir: Path) -> ProjectScan:
    scan = ProjectScan()
    for root, dirs, files in os.walk(project_dir):
        if ".git" in dirs:
            dirs.remove(".git")
        root_path = Path(root)
        file_set = set(files)

        if scan.root_pom is None and root_path == project_dir and "pom.xml" in file_set:
            scan.root_pom = root_path / "pom.xml"

        if not scan.has_tests:
            try:
                relative_root = root_path.relative_to(project_dir).as_posix()
            except ValueError:
                relative_root = ""
            scan.has_tests = (
                relative_root == "src/test/java"
                or relative_root.startswith("src/test/java/")
            ) and any(file_name.endswith(".java") for file_name in files)

        if scan.root_pom is not None and scan.has_tests:
            break

    return scan


def has_tests(project_dir: Path) -> bool:
    return scan_project_structure(project_dir).has_tests

# ---------------------------------------------------------------------------
# Maven
# ---------------------------------------------------------------------------

def mvn_cmd(project_dir: Path, goals: list[str]) -> list[str]:
    wrapper = project_dir / "mvnw"
    if wrapper.exists():
        wrapper.chmod(wrapper.stat().st_mode | 0o111)
        return [str(wrapper), *goals]
    return ["mvn", *goals]


def source_target_flags(declared: str, effective: str) -> list[str]:
    """
    Mantido por compatibilidade com resultados antigos em que o JDK efetivo
    podia ser mais novo que o declarado.
    Não aplica quando o erro P4 indica que o código já usa sintaxe > declarada.
    """
    if not declared.strip():
        return []
    d = canonical(normalize_version(declared))
    if not d.isdigit() or not str(effective).isdigit():
        return []
    if int(effective) > int(d) and int(d) <= 8:
        return [
            f"-Dmaven.compiler.source={d}",
            f"-Dmaven.compiler.target={d}",
        ]
    return []


def compile_project(
    project_dir: Path,
    env: dict[str, str],
    declared: str,
    effective: str,
    skip_source_target: bool = False,
    deadline: float | None = None,
) -> tuple[bool, str]:
    flags = [] if skip_source_target else source_target_flags(declared, effective)
    cmd = mvn_cmd(project_dir, ["compile", "-B", "-q", "-DskipTests"] + flags)
    log.debug("Compilando: %s", " ".join(cmd))
    return run(cmd, project_dir, env, TIMEOUT_COMPILE, deadline)


def run_tests(
    project_dir: Path,
    env: dict[str, str],
    declared: str,
    effective: str,
    skip_source_target: bool = False,
    deadline: float | None = None,
) -> tuple[bool, str]:
    # Mantém as flags de versão do JDK se necessário
    flags = [] if skip_source_target else source_target_flags(declared, effective)
    
    # Adiciona as flags ao comando do Maven
    cmd = mvn_cmd(
        project_dir,
        [
            "test",
            "-B",
            "-q",
            "-DskipITs",
            "-DskipIT",
            "-DskipIntegrationTests",
            "-DfailIfNoTests=false",
        ]
        + flags,
    )
    log.debug("Testando: %s", " ".join(cmd))
    
    return run(cmd, project_dir, env, TIMEOUT_TEST, deadline)

# ---------------------------------------------------------------------------
# Nome local do repositório
# ---------------------------------------------------------------------------

def local_dir_name(repo_name: str) -> str:
    return repo_name.strip().replace("/", "__").replace("\\", "__")

# ---------------------------------------------------------------------------
# Análise de um projeto
# ---------------------------------------------------------------------------

def analyze_project(entry: dict[str, Any], run_test_suite: bool = True) -> ProjectResult:  # noqa: C901
    deadline = time.monotonic() + TIMEOUT_REPOSITORY
    name           = entry.get("repo_name", "").strip()
    repo_url       = entry.get("repo_url",  "").strip()
    java_version   = str(entry.get("java_version", "")).strip()
    build          = entry.get("build", "Maven").strip()
    test_framework = entry.get("test_framework", "").strip()
    expected_commit_sha = str(entry.get("commit_sha") or "").strip() or None
    allow_jdk_upgrade = bool(entry.get("allow_jdk_upgrade"))

    result = ProjectResult(
        name=name, repository_url=repo_url,
        java_version=java_version, effective_java_version=java_version,
        build=build, test_framework=test_framework,
        commit_sha=expected_commit_sha,
    )

    log.info("[%s] Iniciando (Java %s, %s)", name, java_version, build)

    # ── 1. Resolver JDK inicial ──────────────────────────────────────────────
    jdk_path, effective_ver = resolve_jdk(java_version, allow_jdk_upgrade)
    if not jdk_path:
        result.mark_eliminated("jdk_resolution",
                               f"Nenhum JDK disponível para versão '{java_version}'")
        return result

    result.effective_java_version = effective_ver
    env = build_env(jdk_path)

    # ── 2. Clone raso sem submodulos ─────────────────────────────────────────
    dir_name    = local_dir_name(name)
    project_dir = REPOS_DIR / dir_name

    ok, out = clone_with_retry(
        repo_url,
        project_dir,
        shallow=True,
        expected_commit_sha=expected_commit_sha,
        deadline=deadline,
    )
    if not ok:
        result.mark_eliminated("clone", out)
        return result

    actual_commit_sha = current_commit_sha(project_dir)
    if actual_commit_sha:
        result.commit_sha = actual_commit_sha
        if expected_commit_sha and expected_commit_sha != actual_commit_sha:
            log.info(
                "[%s] Commit local difere do SHA minerado; usando HEAD real %s.",
                name,
                actual_commit_sha,
            )

    # ── 3. Validar estrutura com travessia unica ─────────────────────────────
    scan = scan_project_structure(project_dir)
    pom = scan.root_pom
    if pom is None:
        result.mark_eliminated("structure", "pom.xml não encontrado na raiz")
        return result
    if not result.test_framework:
        result.test_framework = detect_test_framework_from_pom(pom)

    # ── 4. Validar compatibilidade com o JDK selecionado ─────────────────────
    pom_ver = read_pom_required_version(pom)
    if pom_ver and int(pom_ver) > int(effective_ver):
        if allow_jdk_upgrade:
            log.info(
                "[%s] pom exige Java %s > JDK atual %s; upgrade automático permitido.",
                name,
                pom_ver,
                effective_ver,
            )
            up_path, up_ver = upgrade_jdk(pom_ver)
            if up_path:
                jdk_path, effective_ver = up_path, up_ver
                result.effective_java_version = effective_ver
                env = build_env(jdk_path)
            else:
                result.mark_eliminated(
                    "jdk_resolution",
                    f"pom exige Java {pom_ver}; nenhum JDK >= {pom_ver} disponível.",
                )
                return result
        else:
            result.mark_eliminated(
                "jdk_resolution",
                f"pom exige Java {pom_ver}, mas o JDK selecionado é {effective_ver}. Upgrade automático desativado.",
            )
            return result

    # ── 5. Detectar testes ───────────────────────────────────────────────────
    if run_test_suite:
        result.has_tests = scan.has_tests
        log.info("[%s] Tem testes: %s | JDK: %s", name, result.has_tests, effective_ver)
        if not result.has_tests:
            result.mark_eliminated("no_tests", "Nenhum teste detectado")
            return result
    else:
        log.info("[%s] Modo somente build | JDK: %s", name, effective_ver)

    # ── 6. Maven com recuperacao sob demanda ─────────────────────────────────
    skip_st = False  # skip_source_target — ativado pelo P4
    if run_test_suite:
        ok, out = run_tests(project_dir, env, java_version, effective_ver, skip_st, deadline)
    else:
        ok, out = compile_project(project_dir, env, java_version, effective_ver, skip_st, deadline)

    if not ok:
        # P4: lambda/diamond em -source mais antigo → remove -source/-target e recompila
        if is_source_target_error(out):
            log.info("[%s] P4: sintaxe Java 8+ com -source legado; removendo flags de source/target.", name)
            skip_st = True
            if run_test_suite:
                ok, out = run_tests(project_dir, env, java_version, effective_ver, skip_st, deadline)
            else:
                ok, out = compile_project(project_dir, env, java_version, effective_ver, skip_st, deadline)

    if not ok:
        # P2/P3a/P3b: versão insuficiente detectada na saída de erro
        needed = detect_required_version_from_error(out)
        if (
            allow_jdk_upgrade
            and needed
            and int(needed) > int(effective_ver)
        ):
            log.info("[%s] precisa Java %s (atual %s); upgrade automático permitido.", name, needed, effective_ver)
            up_path, up_ver = upgrade_jdk(needed)
            if up_path:
                jdk_path, effective_ver = up_path, up_ver
                result.effective_java_version = effective_ver
                env = build_env(jdk_path)
                log.info("[%s] Reexecutando Maven com JDK %s...", name, effective_ver)
                if run_test_suite:
                    ok, out = run_tests(project_dir, env, java_version, effective_ver, skip_st, deadline)
                else:
                    ok, out = compile_project(project_dir, env, java_version, effective_ver, skip_st, deadline)

    if not ok:
        # P5: submódulos faltando → tenta clone completo e recompila
        if is_missing_submodule_error(out):
            log.info("[%s] P5: submódulos ausentes; retentando clone completo.", name)
            shutil.rmtree(project_dir, ignore_errors=True)
            ok_clone, clone_out = clone_with_retry(
                repo_url,
                project_dir,
                shallow=False,
                with_submodules=True,
                expected_commit_sha=expected_commit_sha,
                deadline=deadline,
            )
            if ok_clone:
                if run_test_suite:
                    ok, out = run_tests(project_dir, env, java_version, effective_ver, skip_st, deadline)
                else:
                    ok, out = compile_project(project_dir, env, java_version, effective_ver, skip_st, deadline)
            else:
                out = clone_out  # propaga erro do clone

    result.compiled = ok
    if not ok:
        if run_test_suite:
            stage = classify_test_failure(out)
            if stage in {"tests", "tests_infra"}:
                result.compiled = True
                result.has_tests = True
            result.mark_eliminated(stage, out)
        else:
            result.mark_eliminated("compile", out)
        log.warning("[%s] Maven falhou (JDK efetivo: %s)", name, effective_ver)
        return result

    log.info("[%s] Maven OK (JDK: %s)", name, effective_ver)

    if not run_test_suite:
        return result

    result.tests_passed = True
    log.info("[%s] Testes OK", name)

    return result

# ---------------------------------------------------------------------------
# Limpeza de disco — a cada CLEANUP_BATCH_SIZE projetos concluídos
# ---------------------------------------------------------------------------

def dir_size_mb(path: Path) -> float:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total / (1024 * 1024)


def delete_repo_dir(project_dir: Path, name: str) -> None:
    if not project_dir.exists():
        return
    try:
        shutil.rmtree(project_dir)
        log.info("[cleanup] Removido %s", name)
    except OSError as exc:
        log.warning("[cleanup] Falha ao remover %s: %s", project_dir, exc)


def flush_completed_repos(names: list[str]) -> None:
    removed = 0
    for name in names:
        pd = REPOS_DIR / local_dir_name(name)
        if pd.exists():
            delete_repo_dir(pd, name)
            removed += 1
    log.info("[cleanup] %d repos removidos", removed)

# ---------------------------------------------------------------------------
# Persistência incremental
# ---------------------------------------------------------------------------

def load_existing(output_path: Path) -> dict[str, dict[str, Any]]:
    if not output_path.exists():
        return {}
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
        return {item["name"]: item for item in data if "name" in item}
    except (json.JSONDecodeError, KeyError):
        return {}


def save(
    results: list[dict[str, Any]],
    output_path: Path,
    persist_eliminated_repositories: bool = PERSIST_ELIMINATED_REPOSITORIES,
) -> None:
    persistable_results = filter_persistable_repositories(
        results,
        persist_eliminated_repositories,
    )
    tmp = output_path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(persistable_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(output_path)

# ---------------------------------------------------------------------------
# Métricas finais
# ---------------------------------------------------------------------------

def print_metrics(results: list[dict[str, Any]], elapsed: float) -> None:
    from collections import Counter
    total      = len(results)
    compiled   = sum(1 for r in results if r.get("compiled"))
    has_t      = sum(1 for r in results if r.get("has_tests"))
    passed     = sum(1 for r in results if r.get("tests_passed"))
    eliminated = sum(1 for r in results if r.get("eliminated"))
    mismatched_jdk = sum(1 for r in results
                         if r.get("effective_java_version") != r.get("java_version"))
    pct = lambda n: f"{n/total*100:.1f}%" if total else "—"

    bar = "─" * 54
    print(f"\n{bar}")
    print("  MÉTRICAS FINAIS")
    print(bar)
    print(f"  Total analisado          : {total}")
    print(f"  Compilaram               : {compiled:<4}  ({pct(compiled)})")
    print(f"  Possuem testes           : {has_t:<4}  ({pct(has_t)})")
    print(f"  Testes passaram          : {passed:<4}  ({pct(passed)})")
    print(f"  Eliminados               : {eliminated:<4}  ({pct(eliminated)})")
    print(f"  JDK efetivo divergente   : {mismatched_jdk:<4}  ({pct(mismatched_jdk)})")
    print(f"  Tempo total              : {elapsed:.1f}s")
    print(bar)

    stages = Counter(
        r["error_stage"] for r in results
        if r.get("eliminated") and r.get("error_stage")
    )
    if stages:
        print("\n  Eliminados por etapa:")
        for stage, count in stages.most_common():
            print(f"    {stage:<28} : {count}")
    print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    start = time.time()

    if not INPUT_JSON.exists():
        log.error("Arquivo de entrada não encontrado: %s", INPUT_JSON)
        return 1

    entries: list[dict[str, Any]] = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    log.info("Projetos carregados: %d", len(entries))

    existing = load_existing(OUTPUT_JSON)
    pending  = [e for e in entries if e.get("repo_name") not in existing]
    log.info("Já processados: %d | Pendentes: %d", len(existing), len(pending))

    results_map: dict[str, dict[str, Any]] = dict(existing)
    cleanup_queue: list[str] = []

    progress = tqdm(total=len(pending), desc="Analisando", unit="proj") if tqdm else None

    pending_save = 0  # contador de conclusões ainda não persistidas em disco

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(analyze_project, entry): entry for entry in pending}

            for future in as_completed(futures):
                entry = futures[future]
                name  = entry.get("repo_name", "?")
                try:
                    result = future.result()
                    results_map[result.name] = asdict(result)
                    cleanup_queue.append(result.name)
                except Exception as exc:  # noqa: BLE001
                    log.exception("[%s] Erro inesperado: %s", name, exc)
                    results_map[name] = asdict(ProjectResult(
                        name=name,
                        repository_url=entry.get("repo_url", ""),
                        java_version=str(entry.get("java_version", "")),
                        effective_java_version=str(entry.get("java_version", "")),
                        build=entry.get("build", ""),
                        test_framework=entry.get("test_framework", ""),
                        eliminated=True,
                        error_stage="unexpected",
                        error_message=str(exc),
                    ))
                    cleanup_queue.append(name)
                finally:
                    pending_save += 1
                    if progress:
                        progress.update(1)

                # Grava em lote: evita reescrever o JSON inteiro a cada projeto
                if pending_save >= SAVE_BATCH_SIZE:
                    save(list(results_map.values()), OUTPUT_JSON)
                    pending_save = 0

                if len(cleanup_queue) >= CLEANUP_BATCH_SIZE:
                    log.info("[cleanup] Lote de %d — limpando disco...", CLEANUP_BATCH_SIZE)
                    flush_completed_repos(cleanup_queue)
                    cleanup_queue.clear()
    finally:
        # Garante que nada fique não-persistido, mesmo se o loop for interrompido
        # (exceção não tratada, KeyboardInterrupt, etc.)
        if pending_save > 0:
            save(list(results_map.values()), OUTPUT_JSON)
            pending_save = 0

    if cleanup_queue:
        log.info("[cleanup] Limpeza final de %d repos...", len(cleanup_queue))
        flush_completed_repos(cleanup_queue)
        cleanup_queue.clear()

    if progress:
        progress.close()

    all_results = list(results_map.values())
    save(all_results, OUTPUT_JSON)
    print_metrics(all_results, time.time() - start)
    log.info("Saída salva em: %s", OUTPUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
