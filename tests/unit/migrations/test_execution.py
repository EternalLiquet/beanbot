from __future__ import annotations

import asyncio
from typing import Any

from pytest import MonkeyPatch

from beanbot.migrations import migrate_role_settings


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._iterator = iter(documents)

    def __aiter__(self) -> FakeCursor:
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return next(self._iterator)
        except StopIteration as error:
            raise StopAsyncIteration from error


def _nested_value(document: dict[str, Any], path: str) -> Any:
    value: Any = document
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]] | None = None) -> None:
        self.documents = list(documents or [])
        self.indexes: list[str] = []

    def find(self, query: dict[str, Any]) -> FakeCursor:
        return FakeCursor(self.documents)

    async def find_one(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        return next(
            (
                document
                for document in self.documents
                if all(_nested_value(document, key) == value for key, value in query.items())
            ),
            None,
        )

    async def create_index(self, keys: Any, *, name: str, **options: Any) -> None:
        self.indexes.append(name)

    async def insert_one(self, document: dict[str, Any]) -> None:
        self.documents.append(document)


class FakeDatabase:
    def __init__(self, collection: FakeCollection) -> None:
        self.collection = collection

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collection


class FakeAdmin:
    async def command(self, name: str) -> None:
        return None


class FakeClient:
    def __init__(self, source: FakeCollection, target: FakeCollection) -> None:
        self.admin = FakeAdmin()
        self.databases = {
            "BeanBotDB": FakeDatabase(source),
            "BeanBotPythonDB": FakeDatabase(target),
        }

    def __getitem__(self, name: str) -> FakeDatabase:
        return self.databases[name]

    async def close(self) -> None:
        return None


def _legacy_document(document_id: str) -> dict[str, Any]:
    return {
        "_id": document_id,
        "guildId": "100",
        "channelId": "200",
        "messageId": f"30{document_id}",
        "roleEmotePair": [{"roleId": "400", "emojiId": "500"}],
    }


def _run_migration(monkeypatch: MonkeyPatch, source: FakeCollection, target: FakeCollection) -> Any:
    client = FakeClient(source, target)
    monkeypatch.setattr(migrate_role_settings, "AsyncMongoClient", lambda uri: client)
    return asyncio.run(
        migrate_role_settings.migrate(
            mongo_uri="mongodb://unused",
            source_database="BeanBotDB",
            source_collection="roleSettings",
            target_database="BeanBotPythonDB",
            target_collection="roleMenus",
            apply=True,
        )
    )


def test_apply_preflight_writes_nothing_when_any_source_document_is_invalid(
    monkeypatch: MonkeyPatch,
) -> None:
    source = FakeCollection([_legacy_document("1"), {"_id": "invalid"}])
    target = FakeCollection()

    summary = _run_migration(monkeypatch, source, target)

    assert summary.eligible == 1
    assert summary.invalid == 1
    assert summary.inserted == 0
    assert target.documents == []
    assert target.indexes == []


def test_apply_inserts_into_new_database_after_clean_preflight(monkeypatch: MonkeyPatch) -> None:
    source = FakeCollection([_legacy_document("1")])
    target = FakeCollection()

    summary = _run_migration(monkeypatch, source, target)

    assert summary.eligible == 1
    assert summary.inserted == 1
    assert len(target.documents) == 1
    assert target.indexes == ["role_menu_message_id", "role_menu_legacy_id"]
