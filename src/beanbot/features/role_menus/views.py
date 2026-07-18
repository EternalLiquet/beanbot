from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from beanbot.features.role_menus.models import RoleMenu
from beanbot.features.role_menus.repository import RoleMenuRepository
from beanbot.features.role_menus.service import toggle_member_roles

if TYPE_CHECKING:
    from beanbot.features.role_menus.cog import RoleMenusCog

log = logging.getLogger(__name__)

SELF_ROLE_CUSTOM_ID_PREFIX = "beanbot:self-role-menu:"


def self_role_custom_id(message_id: int) -> str:
    return f"{SELF_ROLE_CUSTOM_ID_PREFIX}{message_id}"


def message_has_current_role_select(message: discord.Message, menu: RoleMenu) -> bool:
    expected_options = tuple((role.role_name[:100], str(role.role_id)) for role in menu.roles)
    expected_custom_id = self_role_custom_id(menu.message_id)

    for row in message.components:
        for component in getattr(row, "children", ()):
            if getattr(component, "custom_id", None) != expected_custom_id:
                continue
            actual_options = tuple(
                (option.label, option.value) for option in getattr(component, "options", ())
            )
            return (
                actual_options == expected_options
                and getattr(component, "min_values", None) == 1
                and getattr(component, "max_values", None) == len(expected_options)
            )
    return False


class SelfRoleSelect(discord.ui.Select["SelfRoleMenuView"]):  # noqa: UP037
    def __init__(self, menu: RoleMenu) -> None:
        options = [
            discord.SelectOption(
                label=role.role_name[:100],
                value=str(role.role_id),
                description="Toggle this role",
            )
            for role in menu.roles
        ]
        super().__init__(
            custom_id=self_role_custom_id(menu.message_id),
            placeholder="Choose one or more roles to toggle",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if view is None:
            return
        await view.apply_selection(interaction, {int(value) for value in self.values})


class SelfRoleMenuView(discord.ui.View):
    def __init__(
        self,
        repository: RoleMenuRepository,
        menu: RoleMenu,
    ) -> None:
        super().__init__(timeout=None)
        self.repository = repository
        self.menu = menu
        self.add_item(SelfRoleSelect(menu))

    async def apply_selection(
        self,
        interaction: discord.Interaction,
        selected_role_ids: set[int],
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This menu only works in a server.",
                ephemeral=True,
            )
            return

        configured_ids = {role.role_id for role in self.menu.roles}
        roles = [
            role
            for role_id in selected_role_ids & configured_ids
            if (role := interaction.guild.get_role(role_id)) is not None
        ]
        if not roles:
            await interaction.response.send_message(
                "Those roles no longer exist.",
                ephemeral=True,
            )
            return

        try:
            result = await toggle_member_roles(interaction.user, roles)
        except (discord.Forbidden, discord.HTTPException):
            log.exception(
                "Could not toggle self roles: guild=%s user=%s menu=%s",
                interaction.guild.id,
                interaction.user.id,
                self.menu.message_id,
            )
            await interaction.response.send_message(
                "I could not update those roles. Check my role hierarchy and permissions.",
                ephemeral=True,
            )
            return

        await self.repository.touch(self.menu.message_id)
        changes: list[str] = []
        if result.added:
            changes.append("Added: " + ", ".join(role.name for role in result.added))
        if result.removed:
            changes.append("Removed: " + ", ".join(role.name for role in result.removed))
        await interaction.response.send_message("\n".join(changes), ephemeral=True)


class RoleMenuBuilderView(discord.ui.View):
    def __init__(self, cog: RoleMenusCog, author_id: int, label: str) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.author_id = author_id
        self.label = label

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "Only the administrator who started this setup can use it.",
            ephemeral=True,
        )
        return False

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select all self-assignable roles",
        min_values=1,
        max_values=20,
    )
    async def select_roles(
        self,
        interaction: discord.Interaction,
        select: discord.ui.RoleSelect[RoleMenuBuilderView],
    ) -> None:
        roles = [value for value in select.values if isinstance(value, discord.Role)]
        await interaction.response.defer(ephemeral=True)
        created = await self.cog.create_role_menu(interaction, self.label, roles)
        if created:
            await interaction.edit_original_response(
                content="Self-role menu created.",
                view=None,
            )
            self.stop()
