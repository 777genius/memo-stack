import asyncio
import json
from pathlib import Path

from memo_stack_adapters.postgres import build_async_engine, create_schema
from sqlalchemy import inspect, text


def _json_value(value: object) -> object:
    if isinstance(value, str):
        return json.loads(value)
    return value


def test_create_schema_upgrades_legacy_profile_schema(tmp_path: Path) -> None:
    async def run() -> dict[str, object]:
        engine = build_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'legacy-profile.db'}")
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        CREATE TABLE memory_spaces (
                            id VARCHAR(80) PRIMARY KEY,
                            slug VARCHAR(160) NOT NULL UNIQUE,
                            name VARCHAR(240) NOT NULL,
                            status VARCHAR(40) NOT NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        CREATE TABLE memory_profiles (
                            id VARCHAR(80) PRIMARY KEY,
                            space_id VARCHAR(80) NOT NULL,
                            external_ref VARCHAR(200) NOT NULL,
                            name VARCHAR(240) NOT NULL,
                            status VARCHAR(40) NOT NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        CREATE TABLE memory_service_tokens (
                            id VARCHAR(80) PRIMARY KEY,
                            space_id VARCHAR(80),
                            profile_ids_json JSON,
                            description VARCHAR(240) NOT NULL,
                            token_hash VARCHAR(80) UNIQUE NOT NULL,
                            permissions_json JSON,
                            status VARCHAR(40) NOT NULL DEFAULT 'active',
                            created_at DATETIME NOT NULL,
                            revoked_at DATETIME
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        CREATE TABLE memory_facts (
                            id VARCHAR(80) PRIMARY KEY,
                            space_id VARCHAR(80) NOT NULL,
                            profile_id VARCHAR(80) NOT NULL,
                            thread_id VARCHAR(80),
                            kind VARCHAR(80) NOT NULL,
                            text TEXT NOT NULL,
                            status VARCHAR(40) NOT NULL,
                            confidence VARCHAR(40) NOT NULL,
                            trust_level VARCHAR(40) NOT NULL,
                            version INTEGER NOT NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memory_spaces (
                            id,
                            slug,
                            name,
                            status,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            'space_legacy',
                            'legacy',
                            'Legacy',
                            'active',
                            '2026-06-01T10:00:00+00:00',
                            '2026-06-01T10:00:00+00:00'
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memory_profiles (
                            id,
                            space_id,
                            external_ref,
                            name,
                            status,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            'profile_legacy',
                            'space_legacy',
                            'default',
                            'Default',
                            'active',
                            '2026-06-01T10:00:00+00:00',
                            '2026-06-01T10:00:00+00:00'
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memory_service_tokens (
                            id,
                            space_id,
                            profile_ids_json,
                            description,
                            token_hash,
                            permissions_json,
                            status,
                            created_at
                        )
                        VALUES (
                            'token_legacy',
                            'space_legacy',
                            '["profile_legacy"]',
                            'legacy scoped',
                            'hash',
                            '["memory:read"]',
                            'active',
                            '2026-06-01T10:00:00+00:00'
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memory_facts (
                            id,
                            space_id,
                            profile_id,
                            kind,
                            text,
                            status,
                            confidence,
                            trust_level,
                            version,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            'fact_legacy',
                            'space_legacy',
                            'profile_legacy',
                            'note',
                            'Legacy fact remains visible after rename.',
                            'active',
                            'high',
                            'high',
                            1,
                            '2026-06-01T10:00:00+00:00',
                            '2026-06-01T10:00:00+00:00'
                        )
                        """
                    )
                )

            await create_schema(engine)

            async with engine.connect() as connection:

                def inspect_legacy_schema(sync_connection) -> dict[str, object]:
                    inspector = inspect(sync_connection)
                    return {
                        "tables": set(inspector.get_table_names()),
                        "fact_columns": {
                            column["name"] for column in inspector.get_columns("memory_facts")
                        },
                        "token_columns": {
                            column["name"]
                            for column in inspector.get_columns("memory_service_tokens")
                        },
                    }

                schema = await connection.run_sync(inspect_legacy_schema)
                token_scope_ids = (
                    await connection.execute(
                        text(
                            """
                            SELECT memory_scope_ids_json
                            FROM memory_service_tokens
                            WHERE id = 'token_legacy'
                            """
                        )
                    )
                ).scalar_one()
                fact_scope_id = (
                    await connection.execute(
                        text("SELECT memory_scope_id FROM memory_facts WHERE id = 'fact_legacy'")
                    )
                ).scalar_one()
                scope_count = (
                    await connection.execute(
                        text("SELECT COUNT(*) FROM memory_scopes WHERE id = 'profile_legacy'")
                    )
                ).scalar_one()
                return {
                    **schema,
                    "token_scope_ids": _json_value(token_scope_ids),
                    "fact_scope_id": fact_scope_id,
                    "scope_count": scope_count,
                }
        finally:
            await engine.dispose()

    result = asyncio.run(run())

    assert "memory_profiles" not in result["tables"]
    assert "memory_scopes" in result["tables"]
    assert "profile_id" not in result["fact_columns"]
    assert "memory_scope_id" in result["fact_columns"]
    assert "profile_ids_json" not in result["token_columns"]
    assert "memory_scope_ids_json" in result["token_columns"]
    assert result["token_scope_ids"] == ["profile_legacy"]
    assert result["fact_scope_id"] == "profile_legacy"
    assert result["scope_count"] == 1


def test_create_schema_maps_partial_legacy_profile_refs_to_existing_scope(
    tmp_path: Path,
) -> None:
    async def run() -> dict[str, object]:
        engine = build_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'partial-profile.db'}")
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        CREATE TABLE memory_spaces (
                            id VARCHAR(80) PRIMARY KEY,
                            slug VARCHAR(160) NOT NULL UNIQUE,
                            name VARCHAR(240) NOT NULL,
                            status VARCHAR(40) NOT NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        CREATE TABLE memory_profiles (
                            id VARCHAR(80) PRIMARY KEY,
                            space_id VARCHAR(80) NOT NULL,
                            external_ref VARCHAR(200) NOT NULL,
                            name VARCHAR(240) NOT NULL,
                            status VARCHAR(40) NOT NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        CREATE TABLE memory_scopes (
                            id VARCHAR(80) PRIMARY KEY,
                            space_id VARCHAR(80) NOT NULL,
                            external_ref VARCHAR(200) NOT NULL,
                            name VARCHAR(240) NOT NULL,
                            status VARCHAR(40) NOT NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        CREATE TABLE memory_facts (
                            id VARCHAR(80) PRIMARY KEY,
                            space_id VARCHAR(80) NOT NULL,
                            profile_id VARCHAR(80) NOT NULL,
                            kind VARCHAR(80) NOT NULL,
                            text TEXT NOT NULL,
                            status VARCHAR(40) NOT NULL,
                            confidence VARCHAR(40) NOT NULL,
                            trust_level VARCHAR(40) NOT NULL,
                            version INTEGER NOT NULL,
                            created_at DATETIME NOT NULL,
                            updated_at DATETIME NOT NULL
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        CREATE TABLE memory_service_tokens (
                            id VARCHAR(80) PRIMARY KEY,
                            space_id VARCHAR(80),
                            profile_ids_json JSON,
                            memory_scope_ids_json JSON,
                            description VARCHAR(240) NOT NULL,
                            token_hash VARCHAR(80) UNIQUE NOT NULL,
                            permissions_json JSON,
                            status VARCHAR(40) NOT NULL DEFAULT 'active',
                            created_at DATETIME NOT NULL,
                            revoked_at DATETIME
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memory_spaces (
                            id,
                            slug,
                            name,
                            status,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            'space_legacy',
                            'legacy',
                            'Legacy',
                            'active',
                            '2026-06-01T10:00:00+00:00',
                            '2026-06-01T10:00:00+00:00'
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memory_profiles (
                            id,
                            space_id,
                            external_ref,
                            name,
                            status,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            'profile_old',
                            'space_legacy',
                            'default',
                            'Default legacy',
                            'active',
                            '2026-06-01T10:00:00+00:00',
                            '2026-06-01T10:00:00+00:00'
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memory_scopes (
                            id,
                            space_id,
                            external_ref,
                            name,
                            status,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            'scope_current',
                            'space_legacy',
                            'default',
                            'Default current',
                            'active',
                            '2026-06-02T10:00:00+00:00',
                            '2026-06-02T10:00:00+00:00'
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memory_facts (
                            id,
                            space_id,
                            profile_id,
                            kind,
                            text,
                            status,
                            confidence,
                            trust_level,
                            version,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            'fact_partial',
                            'space_legacy',
                            'profile_old',
                            'note',
                            'Partial migration fact stays attached.',
                            'active',
                            'high',
                            'high',
                            1,
                            '2026-06-01T10:00:00+00:00',
                            '2026-06-01T10:00:00+00:00'
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memory_service_tokens (
                            id,
                            space_id,
                            profile_ids_json,
                            memory_scope_ids_json,
                            description,
                            token_hash,
                            status,
                            created_at
                        )
                        VALUES (
                            'token_partial',
                            'space_legacy',
                            '["profile_old"]',
                            '["profile_old"]',
                            'partial scoped',
                            'hash_partial',
                            'active',
                            '2026-06-01T10:00:00+00:00'
                        )
                        """
                    )
                )

            await create_schema(engine)

            async with engine.connect() as connection:
                fact_scope_id = (
                    await connection.execute(
                        text("SELECT memory_scope_id FROM memory_facts WHERE id = 'fact_partial'")
                    )
                ).scalar_one()
                token_scope_ids = (
                    await connection.execute(
                        text(
                            """
                            SELECT memory_scope_ids_json
                            FROM memory_service_tokens
                            WHERE id = 'token_partial'
                            """
                        )
                    )
                ).scalar_one()

                def inspect_tables(sync_connection) -> set[str]:
                    return set(inspect(sync_connection).get_table_names())

                return {
                    "tables": await connection.run_sync(inspect_tables),
                    "fact_scope_id": fact_scope_id,
                    "token_scope_ids": _json_value(token_scope_ids),
                }
        finally:
            await engine.dispose()

    result = asyncio.run(run())

    assert "memory_profiles" not in result["tables"]
    assert result["fact_scope_id"] == "scope_current"
    assert result["token_scope_ids"] == ["scope_current"]


def test_create_schema_backfills_partially_upgraded_service_token_scopes(
    tmp_path: Path,
) -> None:
    async def run() -> object:
        engine = build_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'partial-token.db'}")
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        CREATE TABLE memory_service_tokens (
                            id VARCHAR(80) PRIMARY KEY,
                            space_id VARCHAR(80),
                            profile_ids_json JSON,
                            memory_scope_ids_json JSON,
                            description VARCHAR(240) NOT NULL,
                            token_hash VARCHAR(80) UNIQUE NOT NULL,
                            permissions_json JSON,
                            status VARCHAR(40) NOT NULL DEFAULT 'active',
                            created_at DATETIME NOT NULL,
                            revoked_at DATETIME
                        )
                        """
                    )
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO memory_service_tokens (
                            id,
                            profile_ids_json,
                            memory_scope_ids_json,
                            description,
                            token_hash,
                            status,
                            created_at
                        )
                        VALUES (
                            'token_partial',
                            '["profile_partial"]',
                            NULL,
                            'partial scoped',
                            'hash',
                            'active',
                            '2026-06-01T10:00:00+00:00'
                        )
                        """
                    )
                )

            await create_schema(engine)

            async with engine.connect() as connection:
                return (
                    await connection.execute(
                        text(
                            """
                            SELECT memory_scope_ids_json
                            FROM memory_service_tokens
                            WHERE id = 'token_partial'
                            """
                        )
                    )
                ).scalar_one()
        finally:
            await engine.dispose()

    assert _json_value(asyncio.run(run())) == ["profile_partial"]
