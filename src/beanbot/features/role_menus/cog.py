from __future__ import annotations

import logging
from collections.abc import Sequence

import discord
from discord.ext import commands
from pymongo.errors import PyMongoError

from beanbot.discord.bot import BeanBot
from beanbot.features.role_menus.models import RoleMenu, StoredRole
from beanbot.features.role_menus.repository import RoleMenuRepository
from beanbot.features.role_menus.service import LegacyReactionRoleService
from beanbot.features.role_menus.views import (
    RoleMenuBuilderView,
    SelfRoleMenuView,
    message_has_current_role_select,
)

log = logging.getLogger(__name__)


def _safe_allowed_mentions() -> discord.AllowedMentions:
    return discord.AllowedMentions(
        everyone=False,
        users=False,
        roles=False,
        replied_user=False,
    )


class RoleMenusCog(commands.Cog, name="Administrative Commands"):
    def __init__(self, bot: BeanBot) -> None:
        self.bot = bot
        self.repository = (
            RoleMenuRepository(
                bot.mongo_client,
                bot.settings.mongo_database_name,
                bot.settings.mongo_role_menu_collection,
            )
            if bot.mongo_client is not None
            else None
        )
        self.legacy_reaction_service = (
            LegacyReactionRoleService(bot, self.repository) if self.repository is not None else None
        )

    async def cog_load(self) -> None:
        if self.repository is None:
            log.warning("MongoDB is not configured; self-role menus are disabled")
            return
        await self.repository.initialize()
        menus = await self.repository.get_select_menus()
        restored = 0
        for menu in menus:
            if not menu.roles:
                log.error(
                    "Cannot restore self-role menu with no roles: guild=%s channel=%s message=%s",
                    menu.guild_id,
                    menu.channel_id,
                    menu.message_id,
                )
                continue
            if await self._reconcile_select_menu(menu):
                restored += 1
        log.info("Restored %s/%s persistent self-role menus", restored, len(menus))

    async def _reconcile_select_menu(self, menu: RoleMenu) -> bool:
        repository = self.repository
        if repository is None:
            return False

        channel = self.bot.get_channel(menu.channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(menu.channel_id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                log.exception(
                    "Cannot access stored self-role menu channel: guild=%s channel=%s message=%s",
                    menu.guild_id,
                    menu.channel_id,
                    menu.message_id,
                )
                return False

        fetch_message = getattr(channel, "fetch_message", None)
        if fetch_message is None:
            log.error(
                "Stored self-role menu channel cannot fetch messages: guild=%s channel=%s message=%s",
                menu.guild_id,
                menu.channel_id,
                menu.message_id,
            )
            return False

        try:
            message = await fetch_message(menu.message_id)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            log.exception(
                "Cannot access stored self-role menu message: guild=%s channel=%s message=%s",
                menu.guild_id,
                menu.channel_id,
                menu.message_id,
            )
            return False

        view = SelfRoleMenuView(repository, menu)
        if not message_has_current_role_select(message, menu):
            try:
                await message.edit(view=view)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                log.exception(
                    "Cannot repair stored self-role menu: guild=%s channel=%s message=%s",
                    menu.guild_id,
                    menu.channel_id,
                    menu.message_id,
                )
                return False
            log.info(
                "Repaired stored self-role menu component: guild=%s channel=%s message=%s",
                menu.guild_id,
                menu.channel_id,
                menu.message_id,
            )

        self.bot.add_view(view, message_id=menu.message_id)
        return True

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if self.legacy_reaction_service is not None:
            await self.legacy_reaction_service.handle(payload, add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if self.legacy_reaction_service is not None:
            await self.legacy_reaction_service.handle(payload, add=False)

    @commands.hybrid_command(
        name="rolesetting",
        aliases=["role_setting", "rolesettings"],
        description="Create a persistent self-role menu",
    )
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True, embed_links=True)
    async def role_setting(
        self,
        ctx: commands.Context,
        *,
        label: str = "Self-assignable roles",
    ) -> None:
        if self.repository is None:
            await ctx.reply("MongoDB is not configured, so self-role menus are unavailable.")
            return
        normalized_label = label.strip()
        if not normalized_label or len(normalized_label) > 100:
            await ctx.reply("The label must contain between 1 and 100 characters.")
            return

        await ctx.send(
            "Select every role that members should be able to toggle:",
            view=RoleMenuBuilderView(self, ctx.author.id, normalized_label),
            ephemeral=ctx.interaction is not None,
        )

    async def create_role_menu(
        self,
        interaction: discord.Interaction,
        label: str,
        roles: Sequence[discord.Role],
    ) -> bool:
        repository = self.repository
        if repository is None:
            await interaction.followup.send("MongoDB is not configured.", ephemeral=True)
            return False
        guild = interaction.guild
        channel = interaction.channel
        if (
            guild is None
            or not isinstance(channel, discord.abc.Messageable)
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send("This setup only works in a server.", ephemeral=True)
            return False

        invalid_roles = [role for role in roles if role.is_default() or role.managed]
        if invalid_roles:
            await interaction.followup.send(
                "Managed roles and the @everyone role cannot be self-assigned.",
                ephemeral=True,
            )
            return False

        bot_member = guild.me
        if bot_member is None or any(bot_member.top_role <= role for role in roles):
            await interaction.followup.send(
                "My highest role must be above every selected role.",
                ephemeral=True,
            )
            return False
        if interaction.user.id != guild.owner_id and any(
            interaction.user.top_role <= role for role in roles
        ):
            await interaction.followup.send(
                "You can only configure roles below your highest role.",
                ephemeral=True,
            )
            return False

        embed = discord.Embed(
            title=label,
            description="Choose one or more roles below. Selecting a role toggles it on or off.",
        )
        embed.add_field(
            name="Available roles",
            value="\n".join(f"• {role.name}" for role in roles),
            inline=False,
        )

        try:
            role_message = await channel.send(
                embed=embed,
                allowed_mentions=_safe_allowed_mentions(),
            )
        except discord.HTTPException:
            log.exception(
                "Could not publish self-role menu message: guild=%s channel=%s",
                guild.id,
                channel.id,
            )
            try:
                await interaction.followup.send(
                    "I could not publish the self-role menu in this channel.",
                    ephemeral=True,
                )
            except discord.HTTPException:
                log.exception(
                    "Could not report self-role menu publication failure: guild=%s channel=%s",
                    guild.id,
                    channel.id,
                )
            return False

        menu = RoleMenu(
            guild_id=guild.id,
            channel_id=channel.id,
            message_id=role_message.id,
            label=label,
            roles=tuple(
                StoredRole(role_id=role.id, role_name=role.name, position=position)
                for position, role in enumerate(roles)
            ),
        )

        return await self._persist_role_menu(
            repository,
            interaction,
            role_message,
            menu,
            guild.id,
        )

    async def _persist_role_menu(
        self,
        repository: RoleMenuRepository,
        interaction: discord.Interaction,
        role_message: discord.Message,
        menu: RoleMenu,
        guild_id: int,
    ) -> bool:
        try:
            await repository.save(menu)
            await role_message.edit(view=SelfRoleMenuView(repository, menu))
        except (discord.HTTPException, PyMongoError):
            log.exception(
                "Could not create self-role menu: guild=%s message=%s",
                guild_id,
                role_message.id,
            )
            try:
                await repository.delete(role_message.id)
            except PyMongoError:
                log.exception(
                    "Could not remove failed self-role menu record: guild=%s message=%s",
                    guild_id,
                    role_message.id,
                )
            try:
                await role_message.delete()
            except discord.HTTPException:
                log.exception(
                    "Could not remove failed self-role menu message: guild=%s message=%s",
                    guild_id,
                    role_message.id,
                )
            try:
                await interaction.followup.send(
                    "I could not create that self-role menu.",
                    ephemeral=True,
                )
            except discord.HTTPException:
                log.exception(
                    "Could not report failed self-role menu creation: guild=%s message=%s",
                    guild_id,
                    role_message.id,
                )
            return False

        return True


async def setup(bot: BeanBot) -> None:
    await bot.add_cog(RoleMenusCog(bot))
