from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

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


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API para minerar, analisar e filtrar repositorios Java no GitHub.",
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
