# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from typing import Any

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from settings_library.redis import RedisDatabase
from simcore_postgres_database.storage_models import file_meta_data
from simcore_service_storage import _reconciliation_v2 as recon_mod
from simcore_service_storage._reconciliation_v2 import (
    _RECONCILE_CURSOR_KEY,
    _RECONCILE_LIVE_PROJECTS_KEY,
    _RECONCILE_REFERENCED_PATHS_KEY,
    _RECONCILE_SCAN_STARTED_AT_KEY,
    _RECONCILE_TICK_GATE_KEY,
    run_reconciliation_pass,
    run_reconciliation_passes,
)
from simcore_service_storage.modules.db import get_db_engine
from simcore_service_storage.modules.redis import get_redis_client_manager
from simcore_service_storage.modules.s3 import get_s3_client
from types_aiobotocore_s3 import S3Client

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
def app_environment(
    app_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "STORAGE_CLEANER_INTERVAL_S": "null",
            "STORAGE_CLEANER_RECONCILE_ENABLED": "true",
            "STORAGE_CLEANER_RECONCILE_GRACE_PERIOD": "PT0S",
            "STORAGE_CLEANER_RECONCILE_SCAN_BATCH_SIZE": "2",
            "STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS": "0",
        },
    )


@pytest.fixture
def raw_s3_client(initialized_app: FastAPI) -> S3Client:
    return get_s3_client(initialized_app)._client  # noqa: SLF001


@pytest.fixture
async def put_s3_object(
    raw_s3_client: S3Client,
    storage_s3_bucket: str,
) -> AsyncIterator[Callable[..., Awaitable[str]]]:
    uploaded_keys: list[str] = []

    async def _put(key: str, *, body: bytes = b"data") -> str:
        await raw_s3_client.put_object(Bucket=storage_s3_bucket, Key=key, Body=body)
        uploaded_keys.append(key)
        return key

    yield _put

    for key in uploaded_keys:
        await raw_s3_client.delete_object(Bucket=storage_s3_bucket, Key=key)


@pytest.fixture
async def create_fmd_row(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    user_id: UserID,
    faker: Faker,
) -> AsyncIterator[Callable[..., Awaitable[SimcoreS3FileID]]]:
    created_ids: list[SimcoreS3FileID] = []

    async def _create(
        *,
        file_id: SimcoreS3FileID,
        project_id: str | None = None,
        node_id: str | NodeID | None = None,
        created_at: str = "2025-01-01T00:00:00+00:00",
        is_directory: bool = False,
        upload_expires_at: datetime | None = None,
    ) -> SimcoreS3FileID:
        _node_id = f"{node_id}" if node_id else f"{faker.uuid4()}"
        _file_size = 0 if is_directory else int(TypeAdapter(ByteSize).validate_python("1KiB"))

        engine = get_db_engine(initialized_app)
        async with engine.begin() as conn:
            await conn.execute(
                file_meta_data.insert().values(
                    location_id="0",
                    location="simcore.s3",
                    bucket_name=storage_s3_bucket,
                    object_name=file_id,
                    project_id=project_id,
                    node_id=_node_id,
                    user_id=user_id,
                    created_at=created_at,
                    last_modified=created_at,
                    file_id=file_id,
                    file_size=_file_size,
                    entity_tag=None if is_directory else "fake-etag",
                    is_soft_link=False,
                    is_directory=is_directory,
                    upload_expires_at=upload_expires_at,
                    upload_id=None,
                )
            )
        created_ids.append(file_id)
        return file_id

    yield _create

    if created_ids:
        engine = get_db_engine(initialized_app)
        async with engine.begin() as conn:
            await conn.execute(file_meta_data.delete().where(file_meta_data.c.file_id.in_(created_ids)))


async def _assert_fmd_row_exists(app: FastAPI, file_id: SimcoreS3FileID) -> None:
    engine = get_db_engine(app)
    async with engine.begin() as conn:
        rows = (await conn.execute(file_meta_data.select().where(file_meta_data.c.file_id == file_id))).fetchall()
    assert len(rows) == 1


async def _assert_fmd_row_gone(app: FastAPI, file_id: SimcoreS3FileID) -> None:
    engine = get_db_engine(app)
    async with engine.begin() as conn:
        rows = (await conn.execute(file_meta_data.select().where(file_meta_data.c.file_id == file_id))).fetchall()
    assert rows == []


async def _reset_reconcile_redis(app: FastAPI) -> None:
    redis = get_redis_client_manager(app).client(RedisDatabase.LOCKS).redis
    await redis.delete(
        _RECONCILE_CURSOR_KEY,
        _RECONCILE_SCAN_STARTED_AT_KEY,
        _RECONCILE_LIVE_PROJECTS_KEY,
        _RECONCILE_REFERENCED_PATHS_KEY,
        _RECONCILE_TICK_GATE_KEY,
    )


async def test_reconcile_v2_removes_unreachable_api_file(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    put_s3_object: Callable[..., Awaitable[str]],
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
    faker: Faker,
):
    await _reset_reconcile_redis(initialized_app)

    file_id = TypeAdapter(SimcoreS3FileID).validate_python(f"api/{faker.uuid4()}/orphan.bin")
    await create_fmd_row(file_id=file_id, project_id=None)
    await put_s3_object(file_id, body=b"orphan")

    result = await run_reconciliation_pass(initialized_app, force=True)

    assert result.unreachable_removed == 1
    assert result.dangling_removed == 0
    await _assert_fmd_row_gone(initialized_app, file_id)
    listing = await raw_s3_client.list_objects_v2(Bucket=storage_s3_bucket, Prefix=file_id)
    assert "Contents" not in listing


async def test_reconcile_v2_keeps_api_file_referenced_in_workbench(
    initialized_app: FastAPI,
    put_s3_object: Callable[..., Awaitable[str]],
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
    faker: Faker,
):
    await _reset_reconcile_redis(initialized_app)

    file_id = TypeAdapter(SimcoreS3FileID).validate_python(f"api/{faker.uuid4()}/input.bin")
    workbench = {
        f"{faker.uuid4()}": {
            "inputs": {
                "in": {
                    "store": 0,
                    "path": f"{file_id}",
                    "label": "input.bin",
                    "eTag": "fake-etag",
                }
            }
        }
    }
    await create_project(workbench=workbench)
    await create_fmd_row(file_id=file_id, project_id=None)
    await put_s3_object(file_id, body=b"keep")

    result = await run_reconciliation_pass(initialized_app, force=True)

    assert result.total_removed == 0
    await _assert_fmd_row_exists(initialized_app, file_id)


async def test_reconcile_v2_exports_are_not_deleted_by_reachability(
    initialized_app: FastAPI,
    put_s3_object: Callable[..., Awaitable[str]],
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
    user_id: UserID,
    faker: Faker,
):
    await _reset_reconcile_redis(initialized_app)

    missing_export = TypeAdapter(SimcoreS3FileID).validate_python(f"exports/{user_id}/{faker.uuid4()}.zip")
    existing_export = TypeAdapter(SimcoreS3FileID).validate_python(f"exports/{user_id}/{faker.uuid4()}.zip")

    await create_fmd_row(file_id=missing_export, project_id=None)
    await create_fmd_row(file_id=existing_export, project_id=None)
    await put_s3_object(existing_export, body=b"archive")

    result = await run_reconciliation_pass(initialized_app, force=True)

    assert result.unreachable_removed == 0
    assert result.dangling_removed == 1
    await _assert_fmd_row_gone(initialized_app, missing_export)
    await _assert_fmd_row_exists(initialized_app, existing_export)


async def test_reconcile_v2_incremental_cursor_resumes_and_resets(
    initialized_app: FastAPI,
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
):
    await _reset_reconcile_redis(initialized_app)

    real_settings = initialized_app.state.settings
    stub = real_settings.model_copy(update={"STORAGE_CLEANER_RECONCILE_SCAN_BATCH_SIZE": 1})
    monkeypatch.setattr(recon_mod, "get_application_settings", lambda _app: stub)

    file_1 = TypeAdapter(SimcoreS3FileID).validate_python(f"api/{faker.uuid4()}/a.bin")
    file_2 = TypeAdapter(SimcoreS3FileID).validate_python(f"api/{faker.uuid4()}/b.bin")
    await create_fmd_row(file_id=file_1, project_id=None)
    await create_fmd_row(file_id=file_2, project_id=None)

    redis = get_redis_client_manager(initialized_app).client(RedisDatabase.LOCKS).redis

    first = await run_reconciliation_pass(initialized_app)
    assert first.total_removed == 1

    cursor_raw = await redis.get(_RECONCILE_CURSOR_KEY)
    assert cursor_raw is not None

    second = await run_reconciliation_pass(initialized_app)
    assert second.total_removed == 1

    third = await run_reconciliation_pass(initialized_app)
    assert third.total_removed >= 0

    assert await redis.get(_RECONCILE_CURSOR_KEY) is None
    assert await redis.get(_RECONCILE_SCAN_STARTED_AT_KEY) is None


async def test_reconcile_v2_wrap_runs_orphan_project_prefix_cleanup(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    put_s3_object: Callable[..., Awaitable[str]],
    faker: Faker,
):
    await _reset_reconcile_redis(initialized_app)

    project_id = faker.uuid4()
    await put_s3_object(f"{project_id}/node/data.bin", body=b"zombie")

    result = await run_reconciliation_pass(initialized_app)

    assert result.orphan_prefixes_removed == 1
    listing = await raw_s3_client.list_objects_v2(Bucket=storage_s3_bucket, Prefix=f"{project_id}/")
    assert "Contents" not in listing


async def test_run_reconciliation_passes_respects_tick_gate(
    initialized_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
):
    await _reset_reconcile_redis(initialized_app)

    real_settings = initialized_app.state.settings
    stub = real_settings.model_copy(
        update={
            "STORAGE_CLEANER_RECONCILE_ENABLED": True,
        }
    )
    monkeypatch.setattr(recon_mod, "get_application_settings", lambda _app: stub)

    called: list[bool] = []

    async def _fake_reconcile(*_args, **_kwargs):
        called.append(True)
        return recon_mod.ReconciliationCounts()

    monkeypatch.setattr(recon_mod, "run_reconciliation_pass", _fake_reconcile)

    await run_reconciliation_passes(initialized_app)
    await run_reconciliation_passes(initialized_app)

    assert len(called) == 1
