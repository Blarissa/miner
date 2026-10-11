from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os
import sys
from pathlib import Path

from app.core.config import settings


def configure_logging() -> None:
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    logging.getLogger("app").setLevel(logging.INFO)
    logging.getLogger("analyzer").setLevel(logging.INFO)


configure_logging()


from app.api.routes.health import router as health_router
from app.api.routes.repositories import router as repositories_router


# A documentação da API fica em /api/docs: a rota /docs é da página de documentação do front.
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API para minerar, analisar e filtrar repositorios Java no GitHub.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(repositories_router)


# Front compilado (imagem Docker): servido pelo próprio backend, no mesmo endereço e porta.
# Em desenvolvimento a pasta não existe e o front roda à parte (Vite).
FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR", Path(__file__).resolve().parent.parent / "static"))
API_PREFIXES = ("repositories", "health", "api")

if (FRONTEND_DIR / "index.html").is_file():
    if (FRONTEND_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def serve_frontend(path: str):
        if path.split("/", 1)[0] in API_PREFIXES:
            raise HTTPException(status_code=404, detail="Nao encontrado.")
        candidate = (FRONTEND_DIR / path).resolve()
        if path and candidate.is_file() and FRONTEND_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIR / "index.html")

