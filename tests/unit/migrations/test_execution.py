from __future__ import annotations

import asyncio
from typing import Any

from pymongo.errors import DuplicateKeyError, OperationFailure
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
        self.index_specs: dict[str, dict[str, Any]] = {
            "_id_": {"key": [("_id", 1)], "unique": True}
        }
        self.fail_on_insert_number: int | None = None
        self.insert_attempts = 0

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
        if name not in self.index_specs:
            self.indexes.append(name)
        self.index_specs[name] = {"key": list(keys), **options}

    async def index_information(self) -> dict[str, dict[str, Any]]:
        return self.index_specs.copy()

    async def drop_index(self, name: str) -> None:
        self.index_specs.pop(name, None)

    async def insert_one(self, document: dict[str, Any], *, session: FakeSession) -> None:
        self.insert_attempts += 1
        if session.insert_error is not None:
            raise session.insert_error
        if self.fail_on_insert_number == self.insert_attempts:
            raise DuplicateKeyError("late duplicate")
        session.pending.append((self, document))


class FakeDatabase:
    def __init__(self, collections: dict[str, FakeCollection]) -> None:
        self.collections = collections

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


class FakeAdmin:
    async def command(self, name: str) -> None:
        return None


class FakeTransaction:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeTransaction:
        return self

    async def __aexit__(self, error_type: Any, error: Any, traceback: Any) -> None:
        if error_type is None:
            for collection, document in self.session.pending:
                collection.documents.append(document)
        self.session.pending.clear()


class FakeSession:
    def __init__(self, insert_error: OperationFailure | None = None) -> None:
        self.insert_error = insert_error
        self.pending: list[tuple[FakeCollection, dict[str, Any]]] = []

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, error_type: Any, error: Any, traceback: Any) -> None:
        self.pending.clear()

    async def with_transaction(self, callback: Any) -> None:
        async with FakeTransaction(self):
            await callback(self)


class FakeClient:
    def __init__(
        self,
        databases: dict[str, FakeDatabase],
        *,
        insert_error: OperationFailure | None = None,
    ) -> None:
        self.admin = FakeAdmin()
        self.databases = databases
        self.insert_error = insert_error

    def __getitem__(self, name: str) -> FakeDatabase:
        return self.databases[name]

    def start_session(self) -> FakeSession:
        return FakeSession(self.insert_error)

    async def close(self) -> None:
        return None


def _legacy_document(
    document_id: str,
    *,
    message_id: str | None = None,
) -> dict[str, Any]:
    return {
        "_id": document_id,
        "guildId": "100",
        "channelId": "200",
        "messageId": message_id or f"30{document_id}",
        "roleEmotePair": [{"roleId": "400", "emojiId": "500"}],
    }


def _client(
    source: FakeCollection,
    target: FakeCollection,
    *,
    source_database: str = "BeanBotDB",
    source_collection: str = "roleSettings",
    insert_error: OperationFailure | None = None,
) -> FakeClient:
    return FakeClient(
        {
            source_database: FakeDatabase({source_collection: source}),
            "BeanBotPythonDB": FakeDatabase({"roleMenus": target}),
        },
        insert_error=insert_error,
    )


def _run_migration(
    monkeypatch: MonkeyPatch,
    client: FakeClient,
    *,
    source_database: str = "BeanBotDB",
    source_collection: str = "roleSettings",
) -> migrate_role_settings.MigrationSummary:
    monkeypatch.setattr(migrate_role_settings, "AsyncMongoClient", lambda uri: client)
    return asyncio.run(
        migrate_role_settings.migrate(
            mongo_uri="mongodb://unused",
            source_database=source_database,
            source_collection=source_collection,
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

    summary = _run_migration(monkeypatch, _client(source, target))

    assert summary.eligible == 1
    assert summary.invalid == 1
    assert summary.inserted == 0
    assert target.documents == []
    assert target.indexes == []


def test_apply_inserts_into_new_database_after_clean_preflight(monkeypatch: MonkeyPatch) -> None:
    source = FakeCollection([_legacy_document("1")])
    target = FakeCollection()

    summary = _run_migration(monkeypatch, _client(source, target))

    assert summary.eligible == 1
    assert summary.inserted == 1
    assert len(target.documents) == 1
    assert target.indexes == ["role_menu_message_id", "role_menu_migration_source"]


def test_same_legacy_id_from_two_source_namespaces_migrates_independently(
    monkeypatch: MonkeyPatch,
) -> None:
    first = FakeCollection([_legacy_document("same", message_id="301")])
    second = FakeCollection([_legacy_document("same", message_id="302")])
    target = FakeCollection()
    client = FakeClient(
        {
            "SourceA": FakeDatabase({"rolesA": first}),
            "SourceB": FakeDatabase({"rolesB": second}),
            "BeanBotPythonDB": FakeDatabase({"roleMenus": target}),
        }
    )

    first_summary = _run_migration(
        monkeypatch,
        client,
        source_database="SourceA",
        source_collection="rolesA",
    )
    second_summary = _run_migration(
        monkeypatch,
        client,
        source_database="SourceB",
        source_collection="rolesB",
    )

    assert first_summary.inserted == 1
    assert second_summary.inserted == 1
    assert len(target.documents) == 2
    assert {
        (
            document["migration"]["source_database"],
            document["migration"]["source_collection"],
            document["migration"]["legacy_id"],
        )
        for document in target.documents
    } == {("SourceA", "rolesA", "same"), ("SourceB", "rolesB", "same")}


def test_late_duplicate_aborts_every_insert_from_the_transaction(
    monkeypatch: MonkeyPatch,
) -> None:
    source = FakeCollection([_legacy_document("1"), _legacy_document("2")])
    target = FakeCollection()
    target.fail_on_insert_number = 2

    summary = _run_migration(monkeypatch, _client(source, target))

    assert summary.conflicts == 1
    assert summary.inserted == 0
    assert target.documents == []


def test_apply_reports_when_transactions_are_unavailable(monkeypatch: MonkeyPatch) -> None:
    source = FakeCollection([_legacy_document("1")])
    target = FakeCollection()
    transaction_error = OperationFailure(
        "Transaction numbers are only allowed on a replica set member or mongos",
        code=20,
    )

    summary = _run_migration(
        monkeypatch,
        _client(source, target, insert_error=transaction_error),
    )

    assert summary.transactions_unavailable is True
    assert summary.inserted == 0
    assert target.documents == []
