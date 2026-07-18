from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Final

from pymongo import ASCENDING, AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

from beanbot.features.role_menus.models import RoleMenu, menu_from_document, menu_to_document

log = logging.getLogger(__name__)

MESSAGE_INDEX_NAME: Final = "role_menu_message_id"
MIGRATION_SOURCE_INDEX_NAME: Final = "role_menu_migration_source"
LEGACY_MIGRATION_INDEX_NAME: Final = "role_menu_legacy_id"
MIGRATION_SOURCE_INDEX_KEYS: Final = (
    ("migration.source_database", ASCENDING),
    ("migration.source_collection", ASCENDING),
    ("migration.legacy_id", ASCENDING),
)
LEGACY_MIGRATION_INDEX_KEYS: Final = (("migration.legacy_id", ASCENDING),)
MIGRATION_INDEX_FILTER: Final = {"migration.legacy_id": {"$exists": True}}


async def ensure_role_menu_indexes(collection: AsyncCollection[dict[str, Any]]) -> None:
    """Create current indexes and safely replace the legacy migration-ID index."""
    await collection.create_index(
        [("message_id", ASCENDING)],
        name=MESSAGE_INDEX_NAME,
        unique=True,
    )

    migration_index_ready = False
    for name, specification in (await collection.index_information()).items():
        keys = tuple(specification.get("key", ()))
        is_current_migration_index = (
            keys == MIGRATION_SOURCE_INDEX_KEYS
            and specification.get("unique") is True
            and specification.get("partialFilterExpression") == MIGRATION_INDEX_FILTER
        )
        if is_current_migration_index:
            migration_index_ready = True
            continue

        if (
            name in {MIGRATION_SOURCE_INDEX_NAME, LEGACY_MIGRATION_INDEX_NAME}
            or keys == LEGACY_MIGRATION_INDEX_KEYS
        ):
            await collection.drop_index(name)

    if not migration_index_ready:
        await collection.create_index(
            list(MIGRATION_SOURCE_INDEX_KEYS),
            name=MIGRATION_SOURCE_INDEX_NAME,
            unique=True,
            partialFilterExpression=MIGRATION_INDEX_FILTER,
        )


class RoleMenuRepository:
    def __init__(
        self,
        client: AsyncMongoClient[dict[str, Any]],
        database_name: str,
        collection_name: str,
    ) -> None:
        self.collection = client[database_name][collection_name]

    async def initialize(self) -> None:
        await ensure_role_menu_indexes(self.collection)

    async def save(self, menu: RoleMenu) -> None:
        await self.collection.replace_one(
            {"message_id": menu.message_id},
            menu_to_document(menu),
            upsert=True,
        )

    async def get_select_menus(self) -> tuple[RoleMenu, ...]:
        cursor = self.collection.find({"menu_type": "select"}).sort("message_id", ASCENDING)
        documents = await cursor.to_list(None)
        return tuple(menu_from_document(document) for document in documents)

    async def get_reaction_role_id(
        self,
        message_id: int,
        emoji_keys: frozenset[str],
    ) -> int | None:
        document = await self.collection.find_one(
            {"message_id": message_id, "menu_type": "reaction"}
        )
        if document is None:
            return None
        menu = menu_from_document(document)
        match = next((role for role in menu.roles if role.emoji_key in emoji_keys), None)
        if match is None:
            return None
        await self.touch(message_id)
        return match.role_id

    async def touch(self, message_id: int) -> None:
        """Update operational metadata without interrupting role assignment."""
        try:
            await self.collection.update_one(
                {"message_id": message_id},
                {"$set": {"last_accessed": datetime.now(UTC)}},
            )
        except PyMongoError:
            log.warning(
                "Could not update role-menu access metadata: message=%s",
                message_id,
                exc_info=True,
            )

    async def delete(self, message_id: int) -> None:
        await self.collection.delete_one({"message_id": message_id})
