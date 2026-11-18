from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("sandbox")

SECRET_ENV_NAME = re.compile(
    r"(TOKEN|SECRET|PASSW|CREDENTIAL|API_?KEY|PRIVATE_?KEY|DATABASE_URL|GITHUB|^GH_|ASKPASS)",
    re.IGNORECASE,
)


class SandboxUnavailable(RuntimeError):
    """O sandbox é obrigatório (MINER_SANDBOX=required), mas não está funcionando."""


def sandbox_user() -> str:
    return os.environ.get("MINER_SANDBOX_USER", "").strip()


def sandbox_mode() -> str:
    mode = os.environ.get("MINER_SANDBOX", "auto").strip().lower()
    return mode if mode in {"off", "auto", "required"} else "auto"


def scrub_env(env: dict[str, str]) -> dict[str, str]:
    """Remove variáveis que parecem segredo (token, senha, chave, URL do banco)."""
    return {key: value for key, value in env.items() if not SECRET_ENV_NAME.search(key)}


def prepare_env(env: dict[str, str]) -> dict[str, str]:
    """Ambiente que o código de terceiros recebe, com ou sem sandbox."""
    safe = scrub_env(env)
    safe["GIT_TERMINAL_PROMPT"] = "0"
    # Submódulos podem apontar para file://, ssh ou ext::. Só https é permitido.
    safe["GIT_ALLOW_PROTOCOL"] = "https"
    return safe


@lru_cache(maxsize=1)
def _probe() -> tuple[bool, str]:
    user = sandbox_user()
    if not user:
        return False, "MINER_SANDBOX_USER não definido"
    if shutil.which("sudo") is None:
        return False, "sudo não encontrado"
    try:
        result = subprocess.run(
            ["sudo", "-n", "-H", "-u", user, "--", "id", "-un"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"falha ao testar o sandbox: {exc}"
    if result.returncode != 0 or result.stdout.strip() != user:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return False, f"sudo para '{user}' não funcionou: {detail[-1] if detail else result.returncode}"
    return True, "ok"


def is_active() -> bool:
    """True se os comandos de terceiros devem rodar no sandbox.

    Levanta SandboxUnavailable no modo ``required`` quando o sandbox não funciona.
    """
    mode = sandbox_mode()
    if mode == "off":
        return False
    ok, reason = _probe()
    if ok:
        return True
    if mode == "required":
        raise SandboxUnavailable(f"Sandbox obrigatório indisponível: {reason}")
    _warn_once(reason)
    return False


@lru_cache(maxsize=1)
def _warn_once(reason: str) -> None:
    # Fora do Docker (sem MINER_SANDBOX_USER) é o uso normal de desenvolvimento: sem alarde.
    if sandbox_user():
        log.warning("SANDBOX DESLIGADO: %s. O código dos repositórios roda sem isolamento.", reason)


def status() -> dict[str, object]:
    mode = sandbox_mode()
    if mode == "off":
        return {"mode": mode, "active": False, "reason": "desligado por MINER_SANDBOX=off"}
    ok, reason = _probe()
    return {"mode": mode, "user": sandbox_user() or None, "active": ok, "reason": reason}


def wrap_command(command: list[str], env: dict[str, str], timeout: float) -> list[str]:
    """Monta o comando que roda ``command`` como usuário do sandbox.

    ``timeout`` (segundos) é aplicado dentro do sandbox: o servidor não consegue sinalizar
    processos de outro usuário, então o próprio sandbox encerra o comando.
    """
    user = sandbox_user()
    safe = prepare_env(env)
    safe.update({"HOME": f"/home/{user}", "USER": user, "LOGNAME": user})
    assignments = [f"{key}={value}" for key, value in safe.items() if key and "=" not in key]
    return [
        "sudo", "-n", "-H", "-u", user, "--",
        "env", "-i", *assignments,
        "timeout", "-k", "10", str(max(int(timeout), 1)),
        "setpriv", "--no-new-privs", "--",
        *command,
    ]


def launcher_env() -> dict[str, str]:
    """Ambiente do processo que dispara o sudo (só o necessário, sem segredos)."""
    return {"PATH": os.environ.get("PATH", os.defpath)}


def remove_tree(path: Path, base: Path) -> bool:
    """Apaga um diretório de repositório (que pertence ao sandbox quando ele está ativo)."""
    resolved = path.resolve()
    if base.resolve() not in resolved.parents:
        raise ValueError(f"Recusado: {resolved} não está dentro de {base}")
    if not resolved.exists():
        return True
    if is_active():
        command = wrap_command(["rm", "-rf", "--", str(resolved)], os.environ.copy(), 120)
        subprocess.run(command, env=launcher_env(), capture_output=True, timeout=150)
    else:
        shutil.rmtree(resolved, ignore_errors=True)
    return not resolved.exists()


# ---------------------------------------------------------------------------
# Autoteste: docker exec <container> python -m app.services.sandbox
# ---------------------------------------------------------------------------

def _sandbox_sh(script: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(extra_env or {})
    return subprocess.run(
        wrap_command(["sh", "-c", script], env, 30),
        env=launcher_env(), capture_output=True, text=True, timeout=60,
    )


def selftest() -> int:
    from app.core import database
    from app.services.analyzer import REPOS_DIR

    state = status()
    print(f"Sandbox: modo={state['mode']} usuário={state.get('user')} ativo={state['active']} ({state['reason']})")
    if not state["active"]:
        print("O sandbox NÃO está ativo. Nada foi testado.")
        return 2

    user = sandbox_user()
    canary = "canario-segredo-123"
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    r = _sandbox_sh("id -un; id -u")
    lines = r.stdout.split()
    check("roda como o usuário do sandbox", lines[:1] == [user] and lines[1:2] != ["0"], r.stdout.strip())

    r = _sandbox_sh(f"cat '{database.DATABASE_PATH}' >/dev/null 2>&1; echo $?")
    check("não lê o banco de dados", r.stdout.strip() not in {"", "0"}, f"saída={r.stdout.strip()}")

    r = _sandbox_sh(f"cat /proc/{os.getpid()}/environ >/dev/null 2>&1; echo $?")
    check("não lê o ambiente do servidor", r.stdout.strip() not in {"", "0"}, f"saída={r.stdout.strip()}")

    r = _sandbox_sh("env", {"GITHUB_TOKEN": canary, "MINER_CANARY_SECRET": canary})
    check("não recebe variáveis secretas", canary not in r.stdout)

    r = _sandbox_sh("grep -E '^(CapEff|NoNewPrivs):' /proc/self/status")
    capeff = re.search(r"CapEff:\s*(\w+)", r.stdout)
    nnp = re.search(r"NoNewPrivs:\s*(\d)", r.stdout)
    check("sem capabilities", bool(capeff) and set(capeff.group(1)) == {"0"}, r.stdout.replace("\n", " "))
    check("no_new_privs ligado", bool(nnp) and nnp.group(1) == "1")

    r = _sandbox_sh("sudo -n true >/dev/null 2>&1; echo $?")
    check("não vira root via sudo", r.stdout.strip() not in {"", "0"}, f"saída={r.stdout.strip()}")

    app_dir = Path(__file__).resolve().parents[1]
    r = _sandbox_sh(f"touch '{app_dir}/.sandbox-probe' >/dev/null 2>&1; echo $?")
    check("não escreve no código da aplicação", r.stdout.strip() not in {"", "0"}, f"saída={r.stdout.strip()}")

    probe = REPOS_DIR / ".sandbox-probe"
    r = _sandbox_sh(f"touch '{probe}' && rm -f '{probe}' && echo ok")
    check("escreve na pasta dos repositórios", r.stdout.strip() == "ok", (r.stderr or "").strip())

    failed = 0
    for name, ok, detail in checks:
        failed += 0 if ok else 1
        print(f"  [{'OK' if ok else 'FALHA'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
    print("Rede: aberta (esperado nesta versão; o Maven precisa baixar dependências).")
    print("Resultado:", "tudo certo" if not failed else f"{failed} verificação(ões) falharam")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(selftest())
