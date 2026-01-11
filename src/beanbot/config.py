from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    discord_token: str
    dev_guild_id: int = 0
    prefix: str = "%"
    log_level: str = "INFO"
    lead_dev_user_id: int = 0