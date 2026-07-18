from __future__ import annotations

import logging
from typing import Any

import aiohttp
import discord
from discord.ext import commands
from pymongo import AsyncMongoClient

from beanbot.core.config import Settings
from beanbot.features.registry import FEATURE_EXTENSIONS

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
        self.http_session: aiohttp.ClientSession | None = None
        self.mongo_client: AsyncMongoClient[dict[str, Any]] | None = None

    async def setup_hook(self) -> None:
        timeout = aiohttp.ClientTimeout(total=15)
        self.http_session = aiohttp.ClientSession(timeout=timeout)
        if self.settings.mongo_connection_string:
            self.mongo_client = AsyncMongoClient(self.settings.mongo_connection_string)
            await self.mongo_client.admin.command("ping")
            log.info("Connected to MongoDB database: %s", self.settings.mongo_database_name)

        for ext in FEATURE_EXTENSIONS:
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
            if self.http_session and not self.http_session.closed:
                await self.http_session.close()
            if self.mongo_client is not None:
                await self.mongo_client.close()
        finally:
            await super().close()


def create_bot(settings: Settings) -> BeanBot:
    bot = BeanBot(settings)

    @bot.event
    async def on_ready() -> None:
        log.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "unknown")

    return bot
