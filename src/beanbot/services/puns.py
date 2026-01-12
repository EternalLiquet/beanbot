from __future__ import annotations

import csv
import logging
import random
from dataclasses import dataclass
from importlib import resources
from typing import Final

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Pun:
    bad_post: str


class PunRepository:
    _RESOURCE_PACKAGE: Final[str] = "beanbot.resources"
    _RESOURCE_NAME: Final[str] = "puns.csv"

    def __init__(self) -> None:
        self._puns: list[Pun] | None = None

    def _load(self) -> list[Pun]:
        paths = resources.files(self._RESOURCE_PACKAGE).joinpath(self._RESOURCE_NAME)

        # Try encodings in a safe order
        encodings = ["utf-8", "utf-8-sig", "latin-1"]

        last_error: Exception | None = None

        for encoding in encodings:
            try:
                with paths.open("r", encoding=encoding, newline="") as f:
                    reader = csv.DictReader(f)
                    puns: list[Pun] = []

                    for row in reader:
                        value = (row.get("BadPost") or row.get("bad_post") or "").strip()
                        if value:
                            puns.append(Pun(bad_post=value))

                log.info("Loaded %d puns using encoding=%s", len(puns), encoding)
                return puns

            except UnicodeDecodeError as exc:
                last_error = exc
                log.warning("Failed decoding puns.csv with encoding=%s", encoding)
            except Exception:
                log.exception("Unexpected error reading puns.csv with encoding=%s", encoding)
                return []

        log.error("All CSV decoding attempts failed")
        if last_error:
            log.exception(last_error)
        return []
    
    def get_random_pun(self) -> str:
        if self._puns is None:
            self._puns = self._load()
        if not self._puns:
            return "Pun list is empty right now. :("
        return random.choice(self._puns).bad_post
