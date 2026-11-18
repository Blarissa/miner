from typing import Any

import requests
from fastapi import APIRouter

from app.core.config import settings
from app.services import sandbox
from app.services.miner import build_session


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/sandbox")
def health_sandbox() -> dict[str, Any]:
    """Mostra se o código dos repositórios roda isolado (usuário separado, sem segredos)."""
    return sandbox.status()


@router.get("/health/github")
def health_github() -> dict[str, Any]:
    """Diz se o GITHUB_TOKEN do servidor existe e é aceito pelo GitHub. Nunca devolve o token."""
    token = (settings.github_token or "").strip()
    if not token:
        return {
            "configured": False,
            "valid": None,
            "detail": "Variável de ambiente GITHUB_TOKEN não definida no servidor.",
        }
    try:
        with build_session(token) as session:
            response = session.get(f"{settings.github_base_url}/rate_limit", timeout=6)
    except requests.RequestException:
        return {"configured": True, "valid": None, "detail": "Não foi possível falar com o GitHub agora."}
    if response.status_code in (401, 403):
        return {"configured": True, "valid": False, "detail": "O GitHub recusou o token (inválido, expirado ou sem permissão)."}
    if response.status_code != 200:
        return {"configured": True, "valid": None, "detail": f"O GitHub respondeu {response.status_code}."}
    try:
        code_search = response.json()["resources"]["code_search"]
        limits = {"code_search_limit": code_search["limit"], "code_search_remaining": code_search["remaining"]}
    except (ValueError, KeyError, TypeError):
        limits = {}
    return {"configured": True, "valid": True, "detail": "Token aceito pelo GitHub.", **limits}
