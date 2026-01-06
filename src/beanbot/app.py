from __future__ import annotations

import logging

from beanbot.config import Settings
from beanbot.discord.bot import create_bot
from beanbot.logging_config import configure_logging

log = logging.getLogger(__name__)

async def run() -> None:
    settings = Settings()
    configure_logging(settings.log_level)

    bot = create_bot(settings)
    log.info("Starting BeanBot")
    await bot.start(settings.discord_token)