from __future__ import annotations

import logging
import pathlib
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from beanbot.config import Settings

log = logging.getLogger(__name__)

class BeanBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(settings.prefix),
            intents=intents,
            help_command=None,
        )

        self.settings = settings

    async def setup_hook(self) -> None:
        timeout = aiohttp.ClientTimeout(total=15)
        self.http_session = aiohttp.ClientSession(timeout=timeout)

        cogs_dir = pathlib.Path(__file__).resolve().parents[1] / "cogs"
        for file in cogs_dir.glob("*.py"):
            if file.name.startswith("_") or file.name in ("__init__.py"):
                continue
            ext = f"beanbot.cogs.{file.stem}"
            await self.load_extension(ext)
            log.info("Loaded extension: %s", ext)

        if self.settings.dev_guild_id:
            guild = discord.Object(id=self.settings.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced app commands to DEV guild: %s", self.settings.dev_guild_id)
        else:
            log.info("DEV_GUILD_ID not set; skipping slash command sync (prefix commands work)")

    async def close(self) -> None:
        try:
            if self.http and not self.http.closed:
                await self.http.close()
        finally:
            await super().close()

def create_bot(settings: Settings) -> BeanBot:
    bot = BeanBot(settings)

    @bot.event
    async def on_ready() -> None:
        log.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "unknown")

    return bot
