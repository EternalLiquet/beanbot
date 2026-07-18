from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import discord
from pymongo.errors import OperationFailure
from pytest import MonkeyPatch

from beanbot.features.role_menus import views
from beanbot.features.role_menus.models import (
    RoleMenu,
    StoredRole,
    menu_from_document,
    menu_to_document,
    normalize_emoji_key,
)
from beanbot.features.role_menus.repository import RoleMenuRepository
from beanbot.features.role_menus.service import LegacyReactionRoleService, toggle_member_roles
from beanbot.features.role_menus.views import SelfRoleMenuView


class FakeMember:
    def __init__(self, roles: list[Any]) -> None:
        self.id = 50
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
        self.index_specs: dict[str, dict[str, Any]] = {
            "_id_": {"key": [("_id", 1)], "unique": True}
        }
        self.dropped_indexes: list[str] = []
        self.fail_updates = False

    async def create_index(self, keys: Any, *, name: str, **options: Any) -> None:
        self.indexes.append(name)
        self.index_specs[name] = {"key": list(keys), **options}

    async def index_information(self) -> dict[str, dict[str, Any]]:
        return self.index_specs.copy()

    async def drop_index(self, name: str) -> None:
        self.dropped_indexes.append(name)
        self.index_specs.pop(name, None)

    async def replace_one(
        self,
        query: dict[str, Any],
        document: dict[str, Any],
        *,
        upsert: bool,
    ) -> None:
        self.documents = [
            existing for existing in self.documents if existing["message_id"] != query["message_id"]
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
        if self.fail_updates:
            raise OperationFailure("touch failed")
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
    repository = RoleMenuRepository(
        cast(Any, FakeClient(collection)), "BeanBotPythonDB", "roleMenus"
    )
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
        roles=(StoredRole(role_id=11, role_name="Role 11", position=0, emoji_key="custom:99"),),
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

    assert collection.indexes == ["role_menu_message_id", "role_menu_migration_source"]


def test_initialize_replaces_legacy_migration_index() -> None:
    collection = FakeCollection()
    collection.index_specs["role_menu_legacy_id"] = {
        "key": [("migration.legacy_id", 1)],
        "unique": True,
        "sparse": True,
    }
    repository = RoleMenuRepository(
        cast(Any, FakeClient(collection)), "BeanBotPythonDB", "roleMenus"
    )

    asyncio.run(repository.initialize())

    assert collection.dropped_indexes == ["role_menu_legacy_id"]
    assert "role_menu_migration_source" in collection.index_specs
    assert collection.index_specs["role_menu_migration_source"]["key"] == [
        ("migration.source_database", 1),
        ("migration.source_collection", 1),
        ("migration.legacy_id", 1),
    ]


def test_select_menu_role_change_and_response_survive_touch_failure(
    monkeypatch: MonkeyPatch,
) -> None:
    collection = FakeCollection()
    collection.fail_updates = True
    repository = RoleMenuRepository(
        cast(Any, FakeClient(collection)), "BeanBotPythonDB", "roleMenus"
    )
    role = SimpleNamespace(id=10, name="Raiders")
    member = FakeMember([])
    response = SimpleNamespace(messages=[])

    async def send_message(content: str, *, ephemeral: bool) -> None:
        response.messages.append((content, ephemeral))

    response.send_message = send_message
    guild = SimpleNamespace(id=1, get_role=lambda role_id: role if role_id == role.id else None)
    interaction = SimpleNamespace(guild=guild, user=member, response=response)
    menu = RoleMenu(
        guild_id=1,
        channel_id=2,
        message_id=3,
        label="Games",
        roles=(StoredRole(role_id=10, role_name="Raiders", position=0),),
    )
    monkeypatch.setattr(views.discord, "Member", FakeMember)

    async def exercise() -> None:
        view = SelfRoleMenuView(repository, menu)
        await view.apply_selection(cast(discord.Interaction, interaction), {10})

    asyncio.run(exercise())

    assert member.added == (role,)
    assert response.messages == [("Added: Raiders", True)]


def test_legacy_reaction_assignment_survives_touch_failure() -> None:
    collection = FakeCollection()
    collection.fail_updates = True
    menu = RoleMenu(
        guild_id=1,
        channel_id=2,
        message_id=4,
        label="Legacy",
        roles=(StoredRole(role_id=11, role_name="Role 11", position=0, emoji_key="custom:99"),),
        menu_type="reaction",
    )
    collection.documents.append(menu_to_document(menu))
    repository = RoleMenuRepository(
        cast(Any, FakeClient(collection)), "BeanBotPythonDB", "roleMenus"
    )
    role = SimpleNamespace(id=11, name="Role 11")
    member = FakeMember([])
    guild = SimpleNamespace(
        get_role=lambda role_id: role if role_id == role.id else None,
        get_member=lambda user_id: member,
    )
    bot = SimpleNamespace(
        user=SimpleNamespace(id=999),
        get_guild=lambda guild_id: guild,
    )
    payload = SimpleNamespace(
        guild_id=1,
        user_id=50,
        message_id=4,
        emoji=discord.PartialEmoji(name="bean", id=99),
        member=member,
    )

    handled = asyncio.run(
        LegacyReactionRoleService(cast(Any, bot), repository).handle(
            cast(discord.RawReactionActionEvent, payload),
            add=True,
        )
    )

    assert handled is True
    assert member.added == (role,)


def test_normalize_emoji_key_supports_legacy_formats() -> None:
    assert normalize_emoji_key("123") == "custom:123"
    assert normalize_emoji_key("<:bean:123>") == "custom:123"
    assert normalize_emoji_key("\N{FIRE}") == "name:\N{FIRE}"
    assert normalize_emoji_key("bean") == "name:bean"
