"""Single registry of Discord extensions enabled by the composition root."""

from typing import Final

FEATURE_EXTENSIONS: Final[tuple[str, ...]] = (
    "beanbot.features.help.cog",
    "beanbot.features.info.cog",
    "beanbot.features.memes.cog",
    "beanbot.features.ping.cog",
    "beanbot.features.role_menus.cog",
)
