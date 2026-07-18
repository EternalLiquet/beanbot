from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from beanbot.features.memes import cog as meme_cog
from beanbot.features.memes.api import Meme


class FakeContext:
    def __init__(self) -> None:
        self.channel = SimpleNamespace(is_nsfw=lambda: False)
        self.replies: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def reply(self, *args: Any, **kwargs: Any) -> None:
        self.replies.append((args, kwargs))


def test_meme_command_fetches_and_replies_with_embed(monkeypatch: Any) -> None:
    result = Meme(
        post_link="https://example.test/post",
        subreddit="beans",
        title="A bean",
        url="https://example.test/bean.png",
        nsfw=False,
        spoiler=False,
        author="poster",
        ups=42,
    )

    class FakeClient:
        async def get_meme(self, subreddit: str | None = None) -> Meme:
            assert subreddit == "beans"
            return result

    monkeypatch.setattr(meme_cog, "MemeApiClient", lambda session: FakeClient())
    cog = meme_cog.MemeCog(SimpleNamespace(http_session=object()))
    context = FakeContext()

    asyncio.run(meme_cog.MemeCog.meme.callback(cog, context, "beans"))

    assert len(context.replies) == 1
    embed = context.replies[0][1]["embed"]
    assert embed.title == "A bean"
    assert embed.description == "/r/beans"


def test_uwu_command_does_not_run_meme_fetch_logic(monkeypatch: Any) -> None:
    monkeypatch.setattr(meme_cog, "_uwuify", lambda text: f"uwu:{text}")
    cog = meme_cog.MemeCog(SimpleNamespace(http_session=object()))
    context = FakeContext()

    asyncio.run(meme_cog.MemeCog.uwu.callback(cog, context, text="beans"))

    assert context.replies[0][0] == ("uwu:beans",)
    assert len(context.replies) == 1
