from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from importlib import resources
from typing import Final, Optional

import io
import aiohttp
import discord
from discord.ext import commands

from beanbot.discord.bot import BeanBot
from beanbot.services.meme_api import MemeApiClient, MemeApiError
from beanbot.services.puns import PunRepository

log = logging.getLogger(__name__)

def _is_question(text: str) -> bool:
    return text.rstrip().endswith("?")

def _safe_allowed_mentions() -> discord.AllowedMentions:
    return discord.AllowedMentions(everyone=False, users=True, roles=False, replied_user=False)


def _get_random_gordon_gif() -> discord.File | None:
    gordon_gifs = [
        entry for entry in resources.files("beanbot.resources").iterdir()
        if entry.is_file() and entry.name.startswith("gordon") and entry.suffix.lower() == ".gif"
    ]
    if not gordon_gifs:
        return None

    return discord.File(str(random.choice(gordon_gifs)))


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

    def __init__(self, bot: BeanBot, config: Optional[MemeConfig] = None, pun_repo: PunRepository | None = None) -> None:
        self.bot = bot
        self.config = config or MemeConfig()
        self.pun_repo = pun_repo or PunRepository()

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
        if not self.config.toes_url:
            await ctx.reply("Toes URL is not configured yet.")
            return
        await self._send_image_from_url(ctx, self.config.toes_url)

    @commands.hybrid_command(name="yoshimaru", description="The superior ship", short="The superior ship")
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def yoshimaru(self, ctx: commands.Context) -> None:
        if not self.config.yoshimaru_url:
            await ctx.reply("Yoshimaru URL is not configured yet.")
            return
        await self._send_image_from_url(ctx, self.config.yoshimaru_url)

    @commands.hybrid_command(name="echo", description="Gives the bot braincells", short="I'll say what you want me to say")
    @commands.bot_has_permissions(send_messages=True)
    async def echo(self, ctx: commands.Context, *, text: str) -> None:
        if ctx.message:
            try:
                await ctx.message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

        await ctx.send(text, allowed_mentions=_safe_allowed_mentions())

    @commands.hybrid_command(name="8ball", description="Let me predict your future.. for a price")
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    async def eight_ball(self, ctx: commands.Context, *, question: str) -> None:
        if not _is_question(question):
            gordon_gif = _get_random_gordon_gif()
            await ctx.reply(
                f"> {question}\nThat is not a question.",
                file=gordon_gif,
                allowed_mentions=_safe_allowed_mentions(),
            )
            return

        answer = random.choice(self.EIGHT_BALL_RESPONSES)

        await ctx.reply(
            f"> {question}\n{answer}",
            allowed_mentions=_safe_allowed_mentions(),
        )

    @commands.hybrid_command(name="texasnationalbird", description="Texas' official national bird")
    @commands.bot_has_permissions(send_messages=True)
    async def texas_national_bird(self, ctx: commands.Context) -> None:
        await ctx.reply("The Texas Offical National Bird is the AR-15")

    @commands.hybrid_command(name="texasnationalflower", description="Texas' official national flower")
    @commands.bot_has_permissions(send_messages=True)
    async def texas_national_flower(self, ctx: commands.Context) -> None:
        await ctx.reply("The Texas Official National Flower is the Jimmy Dean breakfast taco")

    @commands.hybrid_command(name="texasfacts", description="Get a random Texas fact")
    @commands.bot_has_permissions(send_messages=True)
    async def texas_facts(self, ctx: commands.Context) -> None:
        await ctx.reply(f"Did you know: {random.choice(self.TEXAS_FACTS)}")

    @commands.hybrid_command(name="pun", description="I will give you one PunMaster™ branded pun")
    @commands.bot_has_permissions(send_messages=True)
    async def pun(self, ctx: commands.Context) -> None:
        await ctx.reply(self.pun_repo.get_random_pun())

    @commands.hybrid_command(name="meme", description="Get a random meme (optionally from a subreddit)")
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def meme(self, ctx: commands.Context, subreddit: str | None = None) -> None:
        if not self.bot.http_session:
            await ctx.reply("HTTP client is not initialized.")
            return

        client = MemeApiClient(self.bot.http_session)

        channel_is_nsfw = bool(getattr(ctx.channel, "is_nsfw", lambda: False)())

        attempts = 3 if not channel_is_nsfw else 1
        last_error: Exception | None = None

        for _ in range(attempts):
            try:
                meme = await client.get_meme(subreddit=subreddit.strip() if subreddit else None)
            except MemeApiError as e:
                last_error = e
                break

            if meme.nsfw and not channel_is_nsfw:
                last_error = MemeApiError("Got NSFW meme in non-NSFW channel; retrying.")
                continue

            embed = discord.Embed(
                title=meme.title,
                description=f"/r/{meme.subreddit}",
                url=meme.post_link,
            )
            embed.set_image(url=meme.url)
            if meme.author:
                embed.set_footer(text=f"u/{meme.author} • 👍 {meme.ups}")

            await ctx.reply(embed=embed)
            return

        log.warning("Meme command failed: subreddit=%s error=%s", subreddit, last_error)
        if last_error:
            await ctx.reply(f"Couldn’t fetch a meme: {last_error}")
        else:
            await ctx.reply("Couldn’t fetch a meme right now.")


    async def _send_image_from_url(self, ctx: commands.Context, url: str) -> None:
        if not self.bot.http_session:
            await ctx.reply("HTTP client is not initialized.")
            return

        try:
            async with self.bot.http_session.get(url) as resp:
                resp.raise_for_status()
                content_type = (resp.headers.get("Content-Type") or "").lower()
                data = await resp.read()

            ext = "png"
            if "jpeg" in content_type or "jpg" in content_type:
                ext = "jpg"
            elif "gif" in content_type:
                ext = "gif"
            elif "webp" in content_type:
                ext = "webp"

            file = discord.File(fp=io.BytesIO(data), filename=f"image.{ext}")
            await ctx.reply(file=file)

        except aiohttp.ClientResponseError as e:
            log.warning("Image fetch failed (%s) url=%s", e.status, url)
            await ctx.reply("Could not fetch that image (bad response).")
        except (aiohttp.ClientError, TimeoutError):
            log.warning("Image fetch failed (network/timeout) url=%s", url)
            await ctx.reply("Could not fetch that image (network/timeout).")
        except Exception:
            log.exception("Unexpected error sending image url=%s", url)
            await ctx.reply("Failed to fetch that image.")


async def setup(bot: commands.Bot) -> None:
    config = MemeConfig(
        toes_url = bot.settings.toes_url,
        yoshimaru_url = bot.settings.yoshimaru_url
    )
    await bot.add_cog(MemeCog(bot, config=config, pun_repo=PunRepository()))
