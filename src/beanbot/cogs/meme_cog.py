from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, Optional

import aiohttp
import discord
from discord.ext import commands

from beanbot.discord.bot import BeanBot

log = logging.getLogger(__name__)

def _safe_allowed_mentions() -> discord.AllowedMentions:
    return discord.AllowedMentions(everyone=False, users=True, roles=False, replied_user=False)

@dataclass(frozen=True)
class MemeConfig:
    toes_url: Optional[str] = None
    yoshimaru_url: Optional[str] = None


class MemeCog(commands.Cog, name="Meme Commands"):

    EIGHT_BALL_RESPONSES: Final[list[str]] = [
        "Hell yeah brother",
        "Yeehaw",
        "Yes uwu",
        "The spirit of Texas tells me No",
        "No umu",
        "The answer is yes if you let me suck your toes",
        "It is unclear, let me succ you and try asking again",
        "*succ succ succ* lol you're gay",
    ]
    
    TEXAS_FACTS: Final[list[str]] = [
        "The tale of the Alamo is retold through the stars",
        "The King Ranch in Texas is bigger than the entire state of California",
        "Texas is the largest country in the world",
        "Texas is the largest exporter of Freedom per capita in the world",
        "Texas boasts the largest herd of wild padorus",
        "Astolfo, the most famous Texan cowboy, was born in Europe",
        "More species of cursed bean live in Texas than any other part of the world",
        "The entire country of Texas has 5 Jollibees",
    ]

    def __init__(self, bot: BeanBot, cfg: Optional[MemeConfig] = None) -> None:
        self.bot = bot
        self.cfg = cfg or MemeConfig()

    @commands.hybrid_command(name="succ", description="Astolfo will succ you and call you gay", short="Astolfo will succ an intended target")
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def succ(self, ctx: commands.Context, *, target: str | None = None) -> None:
        author_mention = ctx.author.mention
        target_norm = (target or "").strip()

        if target_norm.lower().startswith("succ "):
            target_norm = target_norm[5:].strip()
        
        me = ctx.me
        if me is not None:
            if "bean bot" in target_norm.lower() or str(me.id) in target_norm:
                target_norm = author_mention
        
        mention = target_norm if target_norm else author_mention

        await ctx.reply(
            f"*succ succ succ* lol you're gay {mention}",
            allowed_mentions=_safe_allowed_mentions()
        )

    @commands.hybrid_command(name="2am", description="There's only one thing to do at 2 AM...", short="McDonald's at 2 AM")
    @commands.bot_has_permissions(send_messages=True)
    async def two_am(self, ctx: commands.Context) -> None:
        await ctx.reply("<:mcdonalds:661337575704887337>")

    @commands.hybrid_command(name="fancy_ocho_ocho", description="Everyone that went to the Music Box is banned", short="The forbidden music box song")
    @commands.bot_has_permissions(send_messages=True)
    async def fancy_ocho_ocho(self, ctx: commands.Context) -> None:
        pages = [
            "One plus one, equals two.",
            "Two plus two, equals four.",
            "Four plus four, equals eight.",
            "Doblehin ang eight.",
            "Tayo'y mag ocho ocho, ocho ocho, mag ocho ocho pa",
        ]
        await ctx.reply("\n".join(pages))

    @commands.hybrid_command(name="420", description="Astolfour-twenty blaze it", short="It's 4:20 somewhere in the world...")
    @commands.bot_has_permissions(send_messages=True)
    async def four_twenty(self, ctx: commands.Context) -> None:
        await ctx.reply("<:420stolfoit:675553715759087618>")

    @commands.hybrid_command(name="toes", description="You've doomed yourself, Hatate", short="Hatate has doomed themselves to a life of toe liking")
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def toes(self, ctx: commands.Context) -> None:
        if not self.cfg.toes_url:
            await ctx.reply("Toes URL is not configured yet.")
            return
        await self._send_image_from_url(ctx, self.cfg.toes_url)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MemeCog(bot))