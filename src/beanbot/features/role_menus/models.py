from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast

MenuType = Literal["select", "reaction"]
_CUSTOM_EMOJI_MENTION = re.compile(r"^<a?:[^:]+:(\d+)>$")


class EmojiLike(Protocol):
    name: str
    id: int | None


@dataclass(frozen=True, slots=True)
class StoredRole:
    role_id: int
    role_name: str
    position: int
    emoji_key: str | None = None


@dataclass(frozen=True, slots=True)
class RoleMenu:
    guild_id: int
    channel_id: int
    message_id: int
    label: str
    roles: tuple[StoredRole, ...]
    menu_type: MenuType = "select"


def menu_to_document(menu: RoleMenu) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "schema_version": 1,
        "menu_type": menu.menu_type,
        "guild_id": menu.guild_id,
        "channel_id": menu.channel_id,
        "message_id": menu.message_id,
        "label": menu.label,
        "roles": [
            {
                "role_id": role.role_id,
                "role_name": role.role_name,
                "position": role.position,
                "emoji_key": role.emoji_key,
            }
            for role in menu.roles
        ],
        "created_at": now,
        "last_accessed": now,
    }


def menu_from_document(document: Mapping[str, Any]) -> RoleMenu:
    roles = tuple(
        StoredRole(
            role_id=int(role["role_id"]),
            role_name=str(role.get("role_name") or f"Role {role['role_id']}"),
            position=int(role.get("position", position)),
            emoji_key=str(role["emoji_key"]) if role.get("emoji_key") is not None else None,
        )
        for position, role in enumerate(document.get("roles", []))
    )
    menu_type = str(document.get("menu_type", "select"))
    if menu_type not in ("select", "reaction"):
        raise ValueError(f"Unsupported role menu type: {menu_type}")
    return RoleMenu(
        guild_id=int(document["guild_id"]),
        channel_id=int(document["channel_id"]),
        message_id=int(document["message_id"]),
        label=str(document.get("label") or "Self-assignable roles"),
        roles=roles,
        menu_type=cast(MenuType, menu_type),
    )


def normalize_emoji_key(value: str | int) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("Emoji key cannot be empty")
    if normalized.startswith(("custom:", "name:")):
        return normalized
    if normalized.isdecimal():
        return f"custom:{normalized}"
    mention = _CUSTOM_EMOJI_MENTION.fullmatch(normalized)
    if mention:
        return f"custom:{mention.group(1)}"
    return f"name:{normalized}"


def reaction_emoji_keys(emoji: EmojiLike) -> frozenset[str]:
    keys = {f"name:{emoji.name}"}
    if emoji.id is not None:
        keys.add(f"custom:{emoji.id}")
    return frozenset(keys)
