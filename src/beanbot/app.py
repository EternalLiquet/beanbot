from __future__ import annotations

import logging

from beanbot.core.config import Settings
from beanbot.core.logging import configure_logging
from beanbot.discord.bot import create_bot

log = logging.getLogger(__name__)


async def run() -> None:
    settings = Settings()  # type: ignore[call-arg]  # Values load from the environment.
    configure_logging(settings.log_level)

    bot = create_bot(settings)
    log.info("Starting BeanBot")
    await bot.start(settings.discord_token)
