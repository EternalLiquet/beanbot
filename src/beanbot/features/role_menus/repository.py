from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING, AsyncMongoClient

from beanbot.features.role_menus.models import RoleMenu, menu_from_document, menu_to_document


class RoleMenuRepository:
    def __init__(
        self,
        client: AsyncMongoClient[dict[str, Any]],
        database_name: str,
        collection_name: str,
    ) -> None:
        self.collection = client[database_name][collection_name]

    async def initialize(self) -> None:
        await self.collection.create_index(
            [("message_id", ASCENDING)],
            name="role_menu_message_id",
            unique=True,
        )
        await self.collection.create_index(
            [("migration.legacy_id", ASCENDING)],
            name="role_menu_legacy_id",
            unique=True,
            sparse=True,
        )

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
        await self.collection.update_one(
            {"message_id": message_id},
            {"$set": {"last_accessed": datetime.now(UTC)}},
        )

    async def delete(self, message_id: int) -> None:
        await self.collection.delete_one({"message_id": message_id})
