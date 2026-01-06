from __future__ import annotations

from discord.ext import commands

class PingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
    
    @commands.hybrid_command(name="ping", description="Check bot latency")
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.reply(f"Pong! {round(self.bot.latency * 1000)}ms")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PingCog(bot))