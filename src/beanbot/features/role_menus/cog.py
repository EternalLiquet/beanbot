from __future__ import annotations

import contextlib
import logging
from collections.abc import Sequence

import discord
from discord.ext import commands
from pymongo.errors import PyMongoError

from beanbot.discord.bot import BeanBot
from beanbot.features.role_menus.models import RoleMenu, StoredRole
from beanbot.features.role_menus.repository import RoleMenuRepository
from beanbot.features.role_menus.service import LegacyReactionRoleService
from beanbot.features.role_menus.views import RoleMenuBuilderView, SelfRoleMenuView

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
        for menu in menus:
            if menu.roles:
                self.bot.add_view(
                    SelfRoleMenuView(self.repository, menu),
                    message_id=menu.message_id,
                )
        log.info("Restored %s persistent self-role menus", len(menus))

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

        role_message = await channel.send(
            embed=embed,
            allowed_mentions=_safe_allowed_mentions(),
        )
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

        try:
            await repository.save(menu)
            await role_message.edit(view=SelfRoleMenuView(repository, menu))
        except (discord.HTTPException, PyMongoError):
            log.exception("Could not create self-role menu in guild %s", guild.id)
            await repository.delete(role_message.id)
            with contextlib.suppress(discord.HTTPException):
                await role_message.delete()
            await interaction.followup.send(
                "I could not create that self-role menu.",
                ephemeral=True,
            )
            return False

        return True


async def setup(bot: BeanBot) -> None:
    await bot.add_cog(RoleMenusCog(bot))
