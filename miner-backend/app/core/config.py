import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GitHub Repository Miner API"
    app_version: str = "1.0.0"

    github_token: str | None = None
    github_base_url: str = "https://api.github.com" 
    github_api_version: str = "2026-03-10"
    database_url: str = "jdbc:sqlite:C:\\Users\\laris\\Desktop\\projeto\\miner-backend\\minerador.db"

    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
