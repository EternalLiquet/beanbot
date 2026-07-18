from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import discord
from pymongo.errors import OperationFailure
from pytest import MonkeyPatch

from beanbot.discord.bot import BeanBot
from beanbot.features.role_menus import cog as role_menu_cog
from beanbot.features.role_menus.cog import RoleMenusCog
from beanbot.features.role_menus.models import RoleMenu, StoredRole
from beanbot.features.role_menus.repository import RoleMenuRepository


def _menu() -> RoleMenu:
    return RoleMenu(
        guild_id=1,
        channel_id=2,
        message_id=3,
        label="Games",
        roles=(StoredRole(role_id=10, role_name="Raiders", position=0),),
    )


class FakeMessage:
    def __init__(self, components: list[Any] | None = None) -> None:
        self.id = 3
        self.components = components or []
        self.edited_view: discord.ui.View | None = None
        self.delete_attempted = False

    async def edit(self, *, view: discord.ui.View) -> None:
        self.edited_view = view

    async def delete(self) -> None:
        self.delete_attempted = True


class FakeChannel:
    def __init__(self, message: FakeMessage) -> None:
        self.message = message

    async def fetch_message(self, message_id: int) -> FakeMessage:
        assert message_id == self.message.id
        return self.message


class FakeBot:
    def __init__(self, channel: FakeChannel | None = None) -> None:
        self.mongo_client = None
        self.settings = object()
        self.channel = channel
        self.added_views: list[tuple[discord.ui.View, int]] = []

    def get_channel(self, channel_id: int) -> FakeChannel | None:
        return self.channel

    async def fetch_channel(self, channel_id: int) -> FakeChannel:
        assert self.channel is not None
        return self.channel

    def add_view(self, view: discord.ui.View, *, message_id: int) -> None:
        self.added_views.append((view, message_id))


class FakeRestoreRepository:
    def __init__(self, menu: RoleMenu) -> None:
        self.menu = menu
        self.initialized = False

    async def initialize(self) -> None:
        self.initialized = True

    async def get_select_menus(self) -> tuple[RoleMenu, ...]:
        return (self.menu,)


def test_startup_reconciliation_repairs_a_stored_menu_without_components() -> None:
    menu = _menu()
    message = FakeMessage()
    bot = FakeBot(FakeChannel(message))
    repository = FakeRestoreRepository(menu)
    cog = RoleMenusCog(cast(BeanBot, bot))
    cog.repository = cast(RoleMenuRepository, repository)

    asyncio.run(cog.cog_load())

    assert repository.initialized is True
    assert message.edited_view is not None
    assert bot.added_views == [(message.edited_view, menu.message_id)]


def test_startup_reconciliation_repairs_a_disabled_select() -> None:
    menu = _menu()
    component = SimpleNamespace(
        type=discord.ComponentType.string_select,
        custom_id="beanbot:self-role-menu:3",
        disabled=True,
        min_values=1,
        max_values=1,
        options=[SimpleNamespace(label="Raiders", value="10")],
    )
    message = FakeMessage([SimpleNamespace(children=[component])])
    bot = FakeBot(FakeChannel(message))
    repository = FakeRestoreRepository(menu)
    cog = RoleMenusCog(cast(BeanBot, bot))
    cog.repository = cast(RoleMenuRepository, repository)

    asyncio.run(cog.cog_load())

    assert message.edited_view is not None
    assert bot.added_views == [(message.edited_view, menu.message_id)]


class FakeFailingRepository:
    def __init__(self) -> None:
        self.delete_attempted = False

    async def save(self, menu: RoleMenu) -> None:
        raise OperationFailure("save failed")

    async def delete(self, message_id: int) -> None:
        self.delete_attempted = True
        raise OperationFailure("cleanup failed")


class FakeFollowup:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bool]] = []

    async def send(self, content: str, *, ephemeral: bool) -> None:
        self.messages.append((content, ephemeral))


class FakePublishRepository:
    def __init__(self) -> None:
        self.save_attempted = False

    async def save(self, menu: RoleMenu) -> None:
        self.save_attempted = True


class FailingPublishChannel:
    id = 2

    async def send(self, **kwargs: Any) -> None:
        response = SimpleNamespace(status=500, reason="Server Error")
        raise discord.HTTPException(cast(Any, response), "publish failed")


class FakeTopRole:
    def __le__(self, other: object) -> bool:
        return False


class FakeAdminMember:
    id = 50
    top_role = FakeTopRole()


class FakeAssignableRole:
    id = 10
    name = "Raiders"
    managed = False

    def is_default(self) -> bool:
        return False


def test_initial_message_failure_reports_error_without_saving(
    monkeypatch: MonkeyPatch,
) -> None:
    bot = FakeBot()
    cog = RoleMenusCog(cast(BeanBot, bot))
    repository = FakePublishRepository()
    cog.repository = cast(RoleMenuRepository, repository)
    channel = FailingPublishChannel()
    member = FakeAdminMember()
    followup = FakeFollowup()
    guild = SimpleNamespace(
        id=1,
        owner_id=member.id,
        me=SimpleNamespace(top_role=FakeTopRole()),
    )
    interaction = SimpleNamespace(
        guild=guild,
        channel=channel,
        user=member,
        followup=followup,
    )
    monkeypatch.setattr(role_menu_cog.discord.abc, "Messageable", FailingPublishChannel)
    monkeypatch.setattr(role_menu_cog.discord, "Member", FakeAdminMember)

    created = asyncio.run(
        cog.create_role_menu(
            cast(discord.Interaction, interaction),
            "Games",
            cast(list[discord.Role], [FakeAssignableRole()]),
        )
    )

    assert created is False
    assert repository.save_attempted is False
    assert followup.messages == [("I could not publish the self-role menu in this channel.", True)]


def test_creation_cleanup_continues_when_repository_cleanup_fails() -> None:
    bot = FakeBot()
    cog = RoleMenusCog(cast(BeanBot, bot))
    repository = FakeFailingRepository()
    message = FakeMessage()
    followup = FakeFollowup()
    interaction = cast(
        discord.Interaction, cast(Any, type("Interaction", (), {"followup": followup})())
    )

    created = asyncio.run(
        cog._persist_role_menu(
            cast(RoleMenuRepository, repository),
            interaction,
            cast(discord.Message, message),
            _menu(),
            1,
        )
    )

    assert created is False
    assert repository.delete_attempted is True
    assert message.delete_attempted is True
    assert followup.messages == [("I could not create that self-role menu.", True)]
