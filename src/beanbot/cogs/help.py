from __future__ import annotations

import discord
from discord.ext import commands


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="help", description="Lists all available commands")
    async def help(self, ctx: commands.Context) -> None:
        # Minimal enterprise-style help; we can enrich later
        embed = discord.Embed(
            title="BeanBot Commands",
            description="Use `%<command>` or `/command`.",
        )

        for cog_name, cog in self.bot.cogs.items():
            items: list[str] = []
            for cmd in cog.get_commands():
                if cmd.hidden:
                    continue
                items.append(f"**{cmd.qualified_name}** — {cmd.short_doc or 'No description'}")

            if items:
                embed.add_field(name=cog_name, value="\n".join(items), inline=False)

        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))