from __future__ import annotations

from datetime import UTC, datetime

import pytest

from beanbot.migrations.migrate_role_settings import transform_legacy_role_setting


def test_transform_legacy_role_setting_preserves_reaction_mapping() -> None:
    last_accessed = datetime(2026, 1, 2, tzinfo=UTC)
    source = {
        "_id": "legacy-id",
        "guildId": "100",
        "channelId": "200",
        "messageId": "300",
        "lastAccessed": last_accessed,
        "roleEmotePair": [
            {"roleId": "400", "emojiId": "500"},
            {"roleId": "401", "emojiId": "501"},
        ],
    }

    transformed = transform_legacy_role_setting(source)

    assert transformed["menu_type"] == "reaction"
    assert transformed["guild_id"] == 100
    assert transformed["channel_id"] == 200
    assert transformed["message_id"] == 300
    assert transformed["last_accessed"] == last_accessed
    assert transformed["migration"]["legacy_id"] == "legacy-id"
    assert transformed["roles"] == [
        {"role_id": 400, "role_name": "Role 400", "position": 0, "emoji_key": "custom:500"},
        {"role_id": 401, "role_name": "Role 401", "position": 1, "emoji_key": "custom:501"},
    ]


def test_transform_legacy_role_setting_accepts_emoji_key() -> None:
    transformed = transform_legacy_role_setting(
        {
            "_id": "legacy-id",
            "guildId": "100",
            "channelId": "200",
            "messageId": "300",
            "roleEmotePair": [{"roleId": "400", "emojiKey": "🔥"}],
        }
    )

    assert transformed["roles"][0]["emoji_key"] == "name:🔥"


def test_transform_legacy_role_setting_rejects_empty_pairs() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        transform_legacy_role_setting(
            {
                "_id": "legacy-id",
                "guildId": "100",
                "channelId": "200",
                "messageId": "300",
                "roleEmotePair": [],
            }
        )
