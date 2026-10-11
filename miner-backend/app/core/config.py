import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_database_url() -> str:
    """Banco SQLite na pasta do usuário (~/.miner), igual em qualquer máquina.

    Para outro lugar, defina DATABASE_URL (ex.: sqlite:////app/data/minerador.db no Docker).
    """
    return f"sqlite:///{Path.home() / '.miner' / 'minerador.db'}"


class Settings(BaseSettings):
    app_name: str = "GitHub Repository Miner API"
    app_version: str = "1.0.0"

    github_token: str | None = None
    github_base_url: str = "https://api.github.com" 
    github_api_version: str = "2026-03-10"
    database_url: str = Field(default_factory=default_database_url)

    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
