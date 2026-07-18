from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import discord

from beanbot.features.role_menus.models import (
    RoleMenu,
    StoredRole,
    menu_from_document,
    menu_to_document,
    normalize_emoji_key,
)
from beanbot.features.role_menus.repository import RoleMenuRepository
from beanbot.features.role_menus.service import toggle_member_roles


class FakeMember:
    def __init__(self, roles: list[Any]) -> None:
        self.roles = roles
        self.added: tuple[Any, ...] = ()
        self.removed: tuple[Any, ...] = ()

    async def add_roles(self, *roles: Any, reason: str) -> None:
        self.added = roles

    async def remove_roles(self, *roles: Any, reason: str) -> None:
        self.removed = roles


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def sort(self, key: str, direction: int) -> FakeCursor:
        self.documents.sort(key=lambda document: document[key])
        return self

    async def to_list(self, length: int | None) -> list[dict[str, Any]]:
        return self.documents


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []
        self.indexes: list[str] = []

    async def create_index(self, keys: Any, *, name: str, **options: Any) -> None:
        self.indexes.append(name)

    async def replace_one(
        self,
        query: dict[str, Any],
        document: dict[str, Any],
        *,
        upsert: bool,
    ) -> None:
        self.documents = [
            existing
            for existing in self.documents
            if existing["message_id"] != query["message_id"]
        ]
        self.documents.append(document)

    def find(self, query: dict[str, Any]) -> FakeCursor:
        return FakeCursor(
            [
                document.copy()
                for document in self.documents
                if all(document.get(key) == value for key, value in query.items())
            ]
        )

    async def find_one(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        return next(
            (
                document
                for document in self.documents
                if all(document.get(key) == value for key, value in query.items())
            ),
            None,
        )

    async def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> None:
        document = await self.find_one(query)
        if document is not None:
            document.update(update["$set"])

    async def delete_one(self, query: dict[str, Any]) -> None:
        self.documents = [
            document
            for document in self.documents
            if not all(document.get(key) == value for key, value in query.items())
        ]


class FakeDatabase:
    def __init__(self, collection: FakeCollection) -> None:
        self.collection = collection

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collection


class FakeClient:
    def __init__(self, collection: FakeCollection) -> None:
        self.database = FakeDatabase(collection)

    def __getitem__(self, name: str) -> FakeDatabase:
        return self.database


def test_role_menu_document_round_trip() -> None:
    menu = RoleMenu(
        guild_id=1,
        channel_id=2,
        message_id=3,
        label="Games",
        roles=(
            StoredRole(role_id=10, role_name="Raiders", position=0),
            StoredRole(role_id=11, role_name="Tabletop", position=1),
        ),
    )

    restored = menu_from_document(menu_to_document(menu))

    assert restored == menu


def test_toggle_member_roles_adds_missing_and_removes_existing() -> None:
    existing = SimpleNamespace(id=10, name="Existing")
    missing = SimpleNamespace(id=11, name="Missing")
    member = FakeMember([existing])

    result = asyncio.run(
        toggle_member_roles(
            cast(discord.Member, member),
            cast(list[discord.Role], [existing, missing]),
        )
    )

    assert member.added == (missing,)
    assert member.removed == (existing,)
    assert result.added == (missing,)
    assert result.removed == (existing,)


def test_mongo_repository_supports_select_and_migrated_reaction_menus() -> None:
    collection = FakeCollection()
    repository = RoleMenuRepository(cast(Any, FakeClient(collection)), "BeanBotPythonDB", "roleMenus")
    select_menu = RoleMenu(
        guild_id=1,
        channel_id=2,
        message_id=3,
        label="Games",
        roles=(StoredRole(role_id=10, role_name="Raiders", position=0),),
    )
    reaction_menu = RoleMenu(
        guild_id=1,
        channel_id=2,
        message_id=4,
        label="Legacy",
        roles=(
            StoredRole(role_id=11, role_name="Role 11", position=0, emoji_key="custom:99"),
        ),
        menu_type="reaction",
    )

    async def exercise() -> None:
        await repository.initialize()
        await repository.save(select_menu)
        await repository.save(reaction_menu)
        assert await repository.get_select_menus() == (select_menu,)
        assert await repository.get_reaction_role_id(4, frozenset({"custom:99"})) == 11
        assert await repository.get_reaction_role_id(4, frozenset({"custom:100"})) is None

    asyncio.run(exercise())

    assert collection.indexes == ["role_menu_message_id", "role_menu_legacy_id"]


def test_normalize_emoji_key_supports_legacy_formats() -> None:
    assert normalize_emoji_key("123") == "custom:123"
    assert normalize_emoji_key("<:bean:123>") == "custom:123"
    assert normalize_emoji_key("🔥") == "name:🔥"
    assert normalize_emoji_key("bean") == "name:bean"
