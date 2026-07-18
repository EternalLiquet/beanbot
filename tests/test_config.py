from __future__ import annotations

from pytest import MonkeyPatch

from beanbot.config import Settings


def test_settings_accept_legacy_csharp_environment_names(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("BEANBOT_BOT_TOKEN", "token")
    monkeypatch.setenv("BEANBOT_MONGO_CONNECTION_STRING", "mongodb://mongo:27017")
    monkeypatch.setenv("BEANBOT_HATOETE_URL", "https://example.test/toes.png")

    settings = Settings(_env_file=None)

    assert settings.discord_token == "token"
    assert settings.mongo_connection_string == "mongodb://mongo:27017"
    assert settings.toes_url == "https://example.test/toes.png"
