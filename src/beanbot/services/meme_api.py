from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

log = logging.getLogger(__name__)

BASE_URL = "https://meme-api.com"


class MemeApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class Meme:
    post_link: str
    subreddit: str
    title: str
    url: str
    nsfw: bool
    spoiler: bool
    author: str
    ups: int


def _parse_meme(payload: dict[str, Any]) -> Meme:
    # Meme API returns fields like postLink, subreddit, title, url, nsfw, spoiler, author, ups. :contentReference[oaicite:4]{index=4}
    try:
        return Meme(
            post_link=str(payload["postLink"]),
            subreddit=str(payload["subreddit"]),
            title=str(payload["title"]),
            url=str(payload["url"]),
            nsfw=bool(payload.get("nsfw", False)),
            spoiler=bool(payload.get("spoiler", False)),
            author=str(payload.get("author", "")),
            ups=int(payload.get("ups", 0)),
        )
    except Exception as exc:
        raise MemeApiError(f"Unexpected meme payload shape: keys={list(payload.keys())}") from exc


class MemeApiClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def get_meme(self, subreddit: Optional[str] = None) -> Meme:
        if subreddit:
            url = f"{BASE_URL}/gimme/{subreddit}"
        else:
            url = f"{BASE_URL}/gimme"

        try:
            async with self._session.get(url) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise MemeApiError(f"Meme API HTTP {resp.status}: {text[:200]}")
                payload = await resp.json()
        except aiohttp.ClientError as exc:
            raise MemeApiError("Network error calling Meme API") from exc

        if isinstance(payload, dict) and "message" in payload and "postLink" not in payload:
            raise MemeApiError(str(payload["message"]))

        if not isinstance(payload, dict):
            raise MemeApiError("Meme API returned non-object JSON")

        return _parse_meme(payload)