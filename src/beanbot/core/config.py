from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    discord_token: str = Field(
        validation_alias=AliasChoices("discord_token", "BEANBOT_BOT_TOKEN", "botToken")
    )
    dev_guild_id: int = 0
    prefix: str = "%"
    log_level: str = "INFO"
    lead_dev_user_id: int = 0
    general_channel_id: int = Field(
        default=0,
        validation_alias=AliasChoices(
            "general_channel_id",
            "BEANBOT_GENERAL_CHANNEL_ID",
            "generalChannelId",
        ),
    )
    toes_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("toes_url", "BEANBOT_HATOETE_URL", "hatoeteUrl"),
    )
    yoshimaru_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "yoshimaru_url",
            "BEANBOT_YOSHIMARU_URL",
            "yoshimaruUrl",
        ),
    )
    mongo_connection_string: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "mongo_connection_string",
            "BEANBOT_MONGO_CONNECTION_STRING",
            "mongoConnectionString",
        ),
    )
    mongo_database_name: str = "BeanBotPythonDB"
    mongo_role_menu_collection: str = "roleMenus"
