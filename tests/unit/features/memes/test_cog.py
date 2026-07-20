from __future__ import annotations

import asyncio
import datetime as dt
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


class FakePunRepository:
    def get_random_pun(self) -> str:
        return "a migrated pun"


class FakeTextChannel:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, content: str, **kwargs: Any) -> None:
        self.messages.append(content)


class FakeBot:
    def __init__(self, channel: FakeTextChannel | None = None) -> None:
        self.http_session = object()
        self.channel = channel
        self.fetch_count = 0

    def get_channel(self, channel_id: int) -> FakeTextChannel | None:
        return self.channel

    async def fetch_channel(self, channel_id: int) -> FakeTextChannel:
        self.fetch_count += 1
        assert self.channel is not None
        return self.channel


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


def test_daily_pun_posts_legacy_message_sequence() -> None:
    channel = FakeTextChannel()
    cog = meme_cog.MemeCog(
        FakeBot(channel),
        config=meme_cog.MemeConfig(daily_pun_channel_id=123),
        pun_repo=FakePunRepository(),
    )

    asyncio.run(cog._post_daily_pun())

    assert channel.messages == [
        meme_cog.DAILY_PUN_INTRO,
        meme_cog.DAILY_PUN_EMOTE,
        "a migrated pun",
    ]


def test_daily_pun_fetches_channel_when_not_cached() -> None:
    channel = FakeTextChannel()
    bot = FakeBot(channel)
    bot.channel = None

    async def fetch_channel(channel_id: int) -> FakeTextChannel:
        bot.fetch_count += 1
        return channel

    bot.fetch_channel = fetch_channel
    cog = meme_cog.MemeCog(
        bot,
        config=meme_cog.MemeConfig(daily_pun_channel_id=123),
        pun_repo=FakePunRepository(),
    )

    asyncio.run(cog._post_daily_pun())

    assert bot.fetch_count == 1
    assert channel.messages[-1] == "a migrated pun"


def test_daily_pun_schedule_uses_chicago_420_pm_with_dst() -> None:
    schedule_time = meme_cog.DAILY_PUN_POST_TIME

    assert schedule_time.hour == 16
    assert schedule_time.minute == 20
    assert schedule_time.tzinfo is meme_cog.DAILY_PUN_TIMEZONE

    winter = dt.datetime(2026, 1, 1, 16, 20, tzinfo=schedule_time.tzinfo)
    summer = dt.datetime(2026, 7, 1, 16, 20, tzinfo=schedule_time.tzinfo)

    assert winter.utcoffset() == dt.timedelta(hours=-6)
    assert summer.utcoffset() == dt.timedelta(hours=-5)
