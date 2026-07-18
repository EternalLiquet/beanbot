from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv
from pymongo import ASCENDING, AsyncMongoClient
from pymongo.errors import DuplicateKeyError

from beanbot.features.role_menus.models import normalize_emoji_key

LEGACY_DATABASE = "BeanBotDB"
LEGACY_COLLECTION = "roleSettings"
DEFAULT_TARGET_DATABASE = "BeanBotPythonDB"
DEFAULT_TARGET_COLLECTION = "roleMenus"


@dataclass(slots=True)
class MigrationSummary:
    discovered: int = 0
    valid: int = 0
    eligible: int = 0
    inserted: int = 0
    already_migrated: int = 0
    conflicts: int = 0
    invalid: int = 0


def transform_legacy_role_setting(document: Mapping[str, Any]) -> dict[str, Any]:
    legacy_id = str(document["_id"])
    guild_id = int(document["guildId"])
    channel_id = int(document["channelId"])
    message_id = int(document["messageId"])
    pairs = document.get("roleEmotePair")
    if not isinstance(pairs, Sequence) or isinstance(pairs, (str, bytes)) or not pairs:
        raise ValueError("roleEmotePair must be a non-empty array")

    roles: list[dict[str, Any]] = []
    for position, pair in enumerate(pairs):
        if not isinstance(pair, Mapping):
            raise ValueError("roleEmotePair entries must be documents")
        role_id = int(pair["roleId"])
        emoji_value = pair.get("emojiId", pair.get("emojiKey"))
        if emoji_value is None:
            raise ValueError("Each role mapping must contain emojiId or emojiKey")
        roles.append(
            {
                "role_id": role_id,
                "role_name": f"Role {role_id}",
                "position": position,
                "emoji_key": normalize_emoji_key(emoji_value),
            }
        )

    now = datetime.now(UTC)
    last_accessed = document.get("lastAccessed")
    if not isinstance(last_accessed, datetime):
        last_accessed = now

    return {
        "schema_version": 1,
        "menu_type": "reaction",
        "guild_id": guild_id,
        "channel_id": channel_id,
        "message_id": message_id,
        "label": "Migrated reaction roles",
        "roles": roles,
        "created_at": now,
        "last_accessed": last_accessed,
        "migration": {
            "source_database": LEGACY_DATABASE,
            "source_collection": LEGACY_COLLECTION,
            "legacy_id": legacy_id,
            "migrated_at": now,
        },
    }


async def migrate(
    *,
    mongo_uri: str,
    source_database: str,
    source_collection: str,
    target_database: str,
    target_collection: str,
    apply: bool,
) -> MigrationSummary:
    if source_database == target_database:
        raise ValueError("The target database must differ from the legacy source database")

    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(mongo_uri)
    summary = MigrationSummary()
    try:
        await client.admin.command("ping")
        source = client[source_database][source_collection]
        target = client[target_database][target_collection]
        candidates: list[dict[str, Any]] = []

        async for legacy_document in source.find({}):
            summary.discovered += 1
            try:
                transformed = transform_legacy_role_setting(legacy_document)
            except (KeyError, TypeError, ValueError):
                summary.invalid += 1
                continue

            transformed["migration"]["source_database"] = source_database
            transformed["migration"]["source_collection"] = source_collection

            summary.valid += 1
            legacy_id = transformed["migration"]["legacy_id"]
            existing = await target.find_one(
                {"migration.legacy_id": legacy_id},
                {"_id": 1},
            )
            if existing is not None:
                summary.already_migrated += 1
                continue

            message_conflict = await target.find_one(
                {"message_id": transformed["message_id"]},
                {"_id": 1},
            )
            if message_conflict is not None:
                summary.conflicts += 1
                continue

            summary.eligible += 1
            candidates.append(transformed)

        if apply and not summary.invalid and not summary.conflicts:
            await target.create_index(
                [("message_id", ASCENDING)],
                name="role_menu_message_id",
                unique=True,
            )
            await target.create_index(
                [("migration.legacy_id", ASCENDING)],
                name="role_menu_legacy_id",
                unique=True,
                sparse=True,
            )
            for transformed in candidates:
                try:
                    await target.insert_one(transformed)
                except DuplicateKeyError:
                    summary.conflicts += 1
                    continue
                summary.inserted += 1
    finally:
        await client.close()

    return summary


def _mongo_uri(cli_value: str | None) -> str:
    value = (
        cli_value
        or os.getenv("mongo_connection_string")  # noqa: SIM112 - pydantic env compatibility
        or os.getenv("BEANBOT_MONGO_CONNECTION_STRING")
        or os.getenv("mongoConnectionString")  # noqa: SIM112 - legacy C# compatibility
    )
    if not value:
        raise ValueError(
            "Set mongo_connection_string or BEANBOT_MONGO_CONNECTION_STRING, or pass --mongo-uri"
        )
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy legacy C# reaction-role documents into Beanbot's new MongoDB schema. "
            "The source database is never modified."
        )
    )
    parser.add_argument("--mongo-uri", help="MongoDB connection URI (defaults to the environment)")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Dotenv file containing the MongoDB URI (default: .env)",
    )
    parser.add_argument("--source-database", default=LEGACY_DATABASE)
    parser.add_argument("--source-collection", default=LEGACY_COLLECTION)
    parser.add_argument("--target-database", default=DEFAULT_TARGET_DATABASE)
    parser.add_argument("--target-collection", default=DEFAULT_TARGET_COLLECTION)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write to the target database; without this flag the command is a dry run",
    )
    return parser


async def _run(arguments: argparse.Namespace) -> int:
    summary = await migrate(
        mongo_uri=_mongo_uri(arguments.mongo_uri),
        source_database=arguments.source_database,
        source_collection=arguments.source_collection,
        target_database=arguments.target_database,
        target_collection=arguments.target_collection,
        apply=arguments.apply,
    )
    mode = "APPLY" if arguments.apply else "DRY RUN"
    print(f"Role settings migration ({mode})")
    print(f"  discovered:       {summary.discovered}")
    print(f"  valid:            {summary.valid}")
    print(f"  eligible:         {summary.eligible}")
    print(f"  inserted:         {summary.inserted}")
    print(f"  already migrated: {summary.already_migrated}")
    print(f"  conflicts:        {summary.conflicts}")
    print(f"  invalid:          {summary.invalid}")
    return 1 if summary.conflicts or summary.invalid else 0


def main() -> None:
    arguments = _parser().parse_args()
    load_dotenv(arguments.env_file)
    try:
        exit_code = asyncio.run(_run(arguments))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
