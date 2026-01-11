from __future__ import annotations

from discord.ext import commands
from beanbot.discord.bot import BeanBot

class InfoCog(commands.Cog, name="Bot Information"):
    def __init__(self, bot: BeanBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="dev", description="Tags Bean Bot's lead developer on Discord", brief="I tag my lead developer")
    async def info(self, ctx: commands.Context) -> None:
        settings = self.bot.settings
        await ctx.reply(f"<@{settings.lead_dev_user_id}> is my lead developer")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InfoCog(bot))