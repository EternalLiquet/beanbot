from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

import discord
from discord.ext import commands

from beanbot.features.role_menus.models import reaction_emoji_keys
from beanbot.features.role_menus.repository import RoleMenuRepository

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RoleToggleResult:
    added: tuple[discord.Role, ...]
    removed: tuple[discord.Role, ...]


class LegacyReactionRoleService:
    def __init__(self, bot: commands.Bot, repository: RoleMenuRepository) -> None:
        self.bot = bot
        self.repository = repository

    async def handle(
        self,
        payload: discord.RawReactionActionEvent,
        *,
        add: bool,
    ) -> bool:
        if payload.guild_id is None or self.bot.user is None:
            return False
        if payload.user_id == self.bot.user.id:
            return False

        role_id = await self.repository.get_reaction_role_id(
            payload.message_id,
            reaction_emoji_keys(payload.emoji),
        )
        if role_id is None:
            return False

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return False
        role = guild.get_role(role_id)
        if role is None:
            log.warning(
                "Migrated reaction role no longer exists: guild=%s message=%s role=%s",
                payload.guild_id,
                payload.message_id,
                role_id,
            )
            return False

        member = payload.member or guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                return False

        try:
            if add:
                await member.add_roles(role, reason="Migrated reaction role added")
            else:
                await member.remove_roles(role, reason="Migrated reaction role removed")
        except (discord.Forbidden, discord.HTTPException):
            log.exception(
                "Could not update migrated reaction role: guild=%s user=%s role=%s add=%s",
                payload.guild_id,
                payload.user_id,
                role_id,
                add,
            )
            return False
        return True


async def toggle_member_roles(
    member: discord.Member,
    roles: Iterable[discord.Role],
) -> RoleToggleResult:
    selected = tuple(roles)
    current_role_ids = {role.id for role in member.roles}
    to_add = tuple(role for role in selected if role.id not in current_role_ids)
    to_remove = tuple(role for role in selected if role.id in current_role_ids)

    if to_add:
        await member.add_roles(*to_add, reason="Self-role menu selection")
    if to_remove:
        await member.remove_roles(*to_remove, reason="Self-role menu selection")

    return RoleToggleResult(added=to_add, removed=to_remove)
