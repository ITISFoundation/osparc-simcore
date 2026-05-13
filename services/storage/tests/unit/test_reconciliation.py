# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from aws_library.s3 import SimcoreS3API
from faker import Faker
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from servicelib.utils_secrets import generate_password
from settings_library.redis import RedisDatabase
from simcore_postgres_database.storage_models import file_meta_data
from simcore_service_storage import _reconciliation as recon_mod
from simcore_service_storage._reconciliation import (
    _CURSOR_REDIS_KEY,
    reconcile_abandoned_multipart_uploads,
    reconcile_db_to_s3,
    reconcile_s3_to_db,
    run_reconciliation_passes,
)
from simcore_service_storage.modules.db import get_db_engine
from simcore_service_storage.modules.redis import get_redis_client_manager
from simcore_service_storage.modules.s3 import get_s3_client
from types_aiobotocore_s3 import S3Client

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]
pytest_simcore_ops_services_selection = ["adminer"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_environment(
    app_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    """Enable all three reconciliation passes and shrink grace to 0s."""
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "STORAGE_CLEANER_RECONCILE_S3_TO_DB_ENABLED": "true",
            "STORAGE_CLEANER_RECONCILE_DB_TO_S3_ENABLED": "true",
            "STORAGE_CLEANER_RECONCILE_MULTIPART_ENABLED": "true",
            "STORAGE_CLEANER_RECONCILE_GRACE_PERIOD": "PT0S",
            "STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS": "0",
        },
    )


@pytest.fixture
def raw_s3_client(initialized_app: FastAPI) -> S3Client:
    return get_s3_client(initialized_app)._client  # noqa: SLF001


@pytest.fixture
async def create_fmd_row(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    user_id: UserID,
) -> AsyncIterator[Callable[..., Awaitable[SimcoreS3FileID]]]:
    """Factory fixture that inserts a file_meta_data row and returns the file_id.

    Accepts overrides for any column via kwargs. Defaults produce a completed
    regular-file entry (upload_expires_at=None, is_directory=False) with an old
    created_at so it's eligible for reconciliation.

    All rows created during the test are deleted on teardown.
    """
    created_ids: list[SimcoreS3FileID] = []

    async def _create(
        *,
        file_id: SimcoreS3FileID | None = None,
        project_id: str | ProjectID | None = None,
        node_id: str | NodeID | None = None,
        created_at: str = "2025-01-01T00:00:00+00:00",
        is_directory: bool = False,
        upload_expires_at: datetime | None = None,
        upload_id: str | None = None,
        file_size: int | None = None,
    ) -> SimcoreS3FileID:
        _project_id = f"{project_id}" if project_id else f"{uuid4()}"
        _node_id = f"{node_id}" if node_id else f"{uuid4()}"
        _file_id = file_id or SimcoreS3FileID(
            f"{_project_id}/{_node_id}/{generate_password(8)}{'' if is_directory else '.bin'}"
        )
        _file_size = (
            file_size
            if file_size is not None
            else (0 if is_directory else int(TypeAdapter(ByteSize).validate_python("1KiB")))
        )

        engine = get_db_engine(initialized_app)
        async with engine.begin() as conn:
            await conn.execute(
                file_meta_data.insert().values(
                    location_id="0",
                    location="simcore.s3",
                    bucket_name=storage_s3_bucket,
                    object_name=_file_id,
                    project_id=_project_id,
                    node_id=_node_id,
                    user_id=user_id,
                    created_at=created_at,
                    last_modified=created_at,
                    file_id=_file_id,
                    file_size=_file_size,
                    entity_tag=None if is_directory else "fake-etag",
                    is_soft_link=False,
                    is_directory=is_directory,
                    upload_expires_at=upload_expires_at,
                    upload_id=upload_id,
                )
            )
        created_ids.append(_file_id)
        return _file_id

    yield _create

    # Teardown: remove all rows created during the test
    if created_ids:
        engine = get_db_engine(initialized_app)
        async with engine.begin() as conn:
            await conn.execute(file_meta_data.delete().where(file_meta_data.c.file_id.in_(created_ids)))


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


async def assert_fmd_row_exists(app: FastAPI, file_id: SimcoreS3FileID) -> None:
    engine = get_db_engine(app)
    async with engine.begin() as conn:
        rows = (await conn.execute(file_meta_data.select().where(file_meta_data.c.file_id == file_id))).fetchall()
    assert len(rows) == 1, f"expected fmd row for {file_id} to exist"


async def assert_fmd_row_gone(app: FastAPI, file_id: SimcoreS3FileID) -> None:
    engine = get_db_engine(app)
    async with engine.begin() as conn:
        rows = (await conn.execute(file_meta_data.select().where(file_meta_data.c.file_id == file_id))).fetchall()
    assert rows == [], f"expected fmd row for {file_id} to be gone"


async def assert_s3_keys_exist(s3_client: S3Client, bucket: str, expected_keys: list[str]) -> None:
    prefixes = {k.rsplit("/", 1)[0] + "/" for k in expected_keys}
    all_keys: set[str] = set()
    for prefix in prefixes:
        listing = await s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        all_keys.update(obj["Key"] for obj in listing.get("Contents", []))
    for key in expected_keys:
        assert key in all_keys, f"S3 key {key} should still exist"


async def assert_s3_prefix_empty(s3_client: S3Client, bucket: str, prefix: str) -> None:
    listing = await s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    assert "Contents" not in listing, f"expected no objects under {prefix}"


async def assert_s3_prefix_has_objects(s3_client: S3Client, bucket: str, prefix: str) -> None:
    listing = await s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    assert "Contents" in listing, f"expected objects under {prefix}"


# ---------------------------------------------------------------------------
# pass (b) reconcile S3 -> DB: orphan project prefixes
# ---------------------------------------------------------------------------


async def test_reconcile_s3_to_db_removes_orphan_project_prefix(
    initialized_app: FastAPI,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
):
    orphan_pid = ProjectID(f"{uuid4()}")
    await raw_s3_client.put_object(Bucket=storage_s3_bucket, Key=f"{orphan_pid}/some-node/data.bin", Body=b"zombie")

    removed = await reconcile_s3_to_db(initialized_app)

    assert removed == 1
    await assert_s3_prefix_empty(raw_s3_client, storage_s3_bucket, f"{orphan_pid}/")


async def test_reconcile_s3_to_db_keeps_prefix_when_project_exists(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
):
    project = await create_project()
    project_id = project["uuid"]
    await raw_s3_client.put_object(Bucket=storage_s3_bucket, Key=f"{project_id}/keep-me.bin", Body=b"keep")

    removed = await reconcile_s3_to_db(initialized_app)

    assert removed == 0
    await assert_s3_prefix_has_objects(raw_s3_client, storage_s3_bucket, f"{project_id}/")


async def test_reconcile_s3_to_db_disabled_is_noop(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    monkeypatch: pytest.MonkeyPatch,
):
    """When the feature flag is OFF the pass returns 0 without scanning S3."""
    real_settings = initialized_app.state.settings
    stub = real_settings.model_copy(update={"STORAGE_CLEANER_RECONCILE_S3_TO_DB_ENABLED": False})
    monkeypatch.setattr(recon_mod, "get_application_settings", lambda _app: stub)

    orphan_pid = ProjectID(f"{uuid4()}")
    await raw_s3_client.put_object(Bucket=storage_s3_bucket, Key=f"{orphan_pid}/keep.bin", Body=b"untouched")

    removed = await reconcile_s3_to_db(initialized_app)

    assert removed == 0
    await assert_s3_prefix_has_objects(raw_s3_client, storage_s3_bucket, f"{orphan_pid}/")


async def test_reconcile_s3_to_db_keeps_prefix_when_fmd_row_exists(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    node_id: NodeID,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
):
    """A prefix is kept if its project_id has an fmd row."""
    prj = await create_project()
    pid = ProjectID(prj["uuid"])
    file_id = SimcoreS3FileID(f"{pid}/{node_id}/data.bin")

    await raw_s3_client.put_object(Bucket=storage_s3_bucket, Key=file_id, Body=b"keep")
    await create_fmd_row(file_id=file_id, project_id=pid, node_id=node_id)

    await reconcile_s3_to_db(initialized_app)

    await assert_s3_prefix_has_objects(raw_s3_client, storage_s3_bucket, f"{pid}/")


async def test_reconcile_s3_to_db_removes_all_files_recursively(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
):
    """All objects under an orphan prefix are deleted, regardless of nesting depth."""
    orphan_pid = ProjectID(f"{uuid4()}")
    s3_keys = [
        f"{orphan_pid}/node-a/file1.bin",
        f"{orphan_pid}/node-a/sub/file2.bin",
        f"{orphan_pid}/node-b/deep/nested/file3.dat",
        f"{orphan_pid}/top-level.txt",
    ]
    for key in s3_keys:
        await raw_s3_client.put_object(Bucket=storage_s3_bucket, Key=key, Body=b"zombie")

    removed = await reconcile_s3_to_db(initialized_app)

    assert removed == 1
    await assert_s3_prefix_empty(raw_s3_client, storage_s3_bucket, f"{orphan_pid}/")


async def test_reconcile_s3_to_db_preserves_files_under_directory(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    node_id: NodeID,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
):
    """S3→DB pass must not remove objects that belong to a directory fmd entry."""
    prj = await create_project()
    pid = ProjectID(prj["uuid"])
    dir_file_id = SimcoreS3FileID(f"{pid}/{node_id}/{generate_password(8)}")

    s3_keys = [
        f"{dir_file_id}/file1.txt",
        f"{dir_file_id}/sub_a/file2.bin",
        f"{dir_file_id}/sub_b/deep/file3.dat",
    ]
    for key in s3_keys:
        await raw_s3_client.put_object(Bucket=storage_s3_bucket, Key=key, Body=b"data")

    await create_fmd_row(file_id=dir_file_id, project_id=pid, node_id=node_id, is_directory=True)

    removed = await reconcile_s3_to_db(initialized_app)

    assert removed == 0
    await assert_s3_keys_exist(raw_s3_client, storage_s3_bucket, s3_keys)


# ---------------------------------------------------------------------------
# pass (c) reconcile abandoned multipart uploads
# ---------------------------------------------------------------------------


async def test_reconcile_multipart_aborts_orphan_upload(
    initialized_app: FastAPI,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    faker: Faker,
):
    orphan_key = f"{uuid4()}/{uuid4()}/orphan-multipart.bin"
    create_resp = await raw_s3_client.create_multipart_upload(Bucket=storage_s3_bucket, Key=orphan_key)
    upload_id = create_resp["UploadId"]

    aborted = await reconcile_abandoned_multipart_uploads(initialized_app)

    assert aborted >= 1
    listing = await raw_s3_client.list_multipart_uploads(Bucket=storage_s3_bucket)
    remaining_ids = {u.get("UploadId") for u in listing.get("Uploads", [])}
    assert upload_id not in remaining_ids


async def test_reconcile_multipart_disabled_is_noop(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    monkeypatch: pytest.MonkeyPatch,
):
    """When the feature flag is OFF, orphan uploads are not aborted."""
    real_settings = initialized_app.state.settings
    stub = real_settings.model_copy(update={"STORAGE_CLEANER_RECONCILE_MULTIPART_ENABLED": False})
    monkeypatch.setattr(recon_mod, "get_application_settings", lambda _app: stub)

    orphan_key = f"{uuid4()}/{uuid4()}/orphan-multipart.bin"
    create_resp = await raw_s3_client.create_multipart_upload(Bucket=storage_s3_bucket, Key=orphan_key)
    upload_id = create_resp["UploadId"]

    aborted = await reconcile_abandoned_multipart_uploads(initialized_app)

    assert aborted == 0
    listing = await raw_s3_client.list_multipart_uploads(Bucket=storage_s3_bucket)
    remaining_ids = {u.get("UploadId") for u in listing.get("Uploads", [])}
    assert upload_id in remaining_ids


async def test_reconcile_multipart_keeps_upload_with_active_fmd_row(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    project_id: ProjectID,
    node_id: NodeID,
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
):
    """An ongoing upload with a matching fmd row (upload_id set) is not aborted."""
    file_id = SimcoreS3FileID(f"{project_id}/{node_id}/{generate_password(8)}.bin")
    create_resp = await raw_s3_client.create_multipart_upload(Bucket=storage_s3_bucket, Key=file_id)
    upload_id = create_resp["UploadId"]

    await create_fmd_row(
        file_id=file_id,
        project_id=project_id,
        node_id=node_id,
        upload_expires_at=datetime(2099, 1, 1),  # noqa: DTZ001
        upload_id=upload_id,
    )

    await reconcile_abandoned_multipart_uploads(initialized_app)

    listing = await raw_s3_client.list_multipart_uploads(Bucket=storage_s3_bucket)
    remaining_ids = {u.get("UploadId") for u in listing.get("Uploads", [])}
    assert upload_id in remaining_ids


# ---------------------------------------------------------------------------
# pass (a) reconcile DB -> S3: dangling fmd rows
# ---------------------------------------------------------------------------


async def test_reconcile_db_to_s3_removes_fmd_row_with_no_s3_object(
    initialized_app: FastAPI,
    project_id: ProjectID,
    node_id: NodeID,
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
):
    file_id = await create_fmd_row(project_id=project_id, node_id=node_id)

    removed = await reconcile_db_to_s3(initialized_app)

    assert removed >= 1
    await assert_fmd_row_gone(initialized_app, file_id)


async def test_reconcile_db_to_s3_disabled_is_noop(
    initialized_app: FastAPI,
    project_id: ProjectID,
    node_id: NodeID,
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
    monkeypatch: pytest.MonkeyPatch,
):
    """When the feature flag is OFF the pass returns 0 without scanning."""
    real_settings = initialized_app.state.settings
    stub = real_settings.model_copy(update={"STORAGE_CLEANER_RECONCILE_DB_TO_S3_ENABLED": False})
    monkeypatch.setattr(recon_mod, "get_application_settings", lambda _app: stub)

    file_id = await create_fmd_row(project_id=project_id, node_id=node_id)

    removed = await reconcile_db_to_s3(initialized_app)

    assert removed == 0
    await assert_fmd_row_exists(initialized_app, file_id)


async def test_reconcile_db_to_s3_respects_grace_period(
    initialized_app: FastAPI,
    project_id: ProjectID,
    node_id: NodeID,
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
    monkeypatch: pytest.MonkeyPatch,
):
    """A recently-created fmd row should NOT be deleted even if its S3 object is missing."""
    real_settings = initialized_app.state.settings
    stub = real_settings.model_copy(update={"STORAGE_CLEANER_RECONCILE_GRACE_PERIOD": timedelta(hours=1)})
    monkeypatch.setattr(recon_mod, "get_application_settings", lambda _app: stub)

    now_iso = datetime.now(tz=UTC).isoformat()
    file_id = await create_fmd_row(project_id=project_id, node_id=node_id, created_at=now_iso)

    removed = await reconcile_db_to_s3(initialized_app)

    assert removed == 0
    await assert_fmd_row_exists(initialized_app, file_id)


async def test_reconcile_db_to_s3_cursor_advances_across_invocations(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    node_id: NodeID,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
    monkeypatch: pytest.MonkeyPatch,
):
    """Cursor-based batching: the cursor persists across calls and resets after a full cycle."""
    real_settings = initialized_app.state.settings
    stub = real_settings.model_copy(update={"STORAGE_CLEANER_RECONCILE_BATCH_SIZE": 1})
    monkeypatch.setattr(recon_mod, "get_application_settings", lambda _app: stub)

    engine = get_db_engine(initialized_app)
    async with engine.begin() as conn:
        await conn.execute(file_meta_data.delete())
    redis = get_redis_client_manager(initialized_app).client(RedisDatabase.LOCKS).redis
    await redis.delete(_CURSOR_REDIS_KEY)

    prj1 = await create_project()
    prj2 = await create_project()
    project_ids = sorted([prj1["uuid"], prj2["uuid"]])

    file_ids = []
    for pid in project_ids:
        fid = await create_fmd_row(project_id=pid, node_id=node_id)
        file_ids.append(fid)

    # First call: batch_size=1, processes first project only
    removed_1 = await reconcile_db_to_s3(initialized_app)
    assert removed_1 == 1

    cursor_val = await redis.get(_CURSOR_REDIS_KEY)
    assert cursor_val is not None
    cursor_str = cursor_val if isinstance(cursor_val, str) else cursor_val.decode()
    assert cursor_str == project_ids[0]

    # Second call: processes second project
    removed_2 = await reconcile_db_to_s3(initialized_app)
    assert removed_2 == 1

    cursor_val = await redis.get(_CURSOR_REDIS_KEY)
    assert cursor_val is not None
    cursor_str = cursor_val if isinstance(cursor_val, str) else cursor_val.decode()
    assert cursor_str == project_ids[1]

    # Third call: no more projects, cycle resets
    removed_3 = await reconcile_db_to_s3(initialized_app)
    assert removed_3 == 0
    cursor_val = await redis.get(_CURSOR_REDIS_KEY)
    assert cursor_val is None

    # Both rows gone
    async with engine.begin() as conn:
        rows = (await conn.execute(file_meta_data.select().where(file_meta_data.c.file_id.in_(file_ids)))).fetchall()
    assert rows == []


async def test_reconcile_db_to_s3_null_project_id_does_not_stall_cursor(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    node_id: NodeID,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
    monkeypatch: pytest.MonkeyPatch,
):
    """A NULL project_id fmd row must not prevent the cursor from advancing."""
    real_settings = initialized_app.state.settings
    stub = real_settings.model_copy(update={"STORAGE_CLEANER_RECONCILE_BATCH_SIZE": 1})
    monkeypatch.setattr(recon_mod, "get_application_settings", lambda _app: stub)

    engine = get_db_engine(initialized_app)
    async with engine.begin() as conn:
        await conn.execute(file_meta_data.delete())
    redis = get_redis_client_manager(initialized_app).client(RedisDatabase.LOCKS).redis
    await redis.delete(_CURSOR_REDIS_KEY)

    # Create an fmd row via the fixture (needs an existing project for FK),
    # then set its project_id to NULL
    tmp_prj = await create_project()
    null_file_id = await create_fmd_row(project_id=tmp_prj["uuid"], node_id=node_id)
    async with engine.begin() as conn:
        await conn.execute(
            file_meta_data.update().where(file_meta_data.c.file_id == null_file_id).values(project_id=None)
        )

    # Also add a real project fmd row so we know the cursor completes
    prj = await create_project()
    await create_fmd_row(project_id=prj["uuid"], node_id=node_id)

    # Run twice: first call should process the real project (skipping NULL);
    # second call should reset (cycle complete), not stall.
    removed_1 = await reconcile_db_to_s3(initialized_app)
    removed_2 = await reconcile_db_to_s3(initialized_app)

    assert removed_1 + removed_2 >= 1, "Real dangling row should be removed"

    # After two calls the cursor must have reset (cycle done), not stuck
    cursor_val = await redis.get(_CURSOR_REDIS_KEY)
    assert cursor_val is None, "Cursor should reset after full sweep"


async def test_reconcile_db_to_s3_force_skips_cursor(
    initialized_app: FastAPI,
    project_id: ProjectID,
    node_id: NodeID,
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
):
    """force=True processes everything in one shot, ignoring cursor."""
    await create_fmd_row(project_id=project_id, node_id=node_id)

    removed = await reconcile_db_to_s3(initialized_app, force=True)

    assert removed >= 1
    redis = get_redis_client_manager(initialized_app).client(RedisDatabase.LOCKS).redis
    cursor_val = await redis.get(_CURSOR_REDIS_KEY)
    assert cursor_val is None


async def test_reconcile_db_to_s3_preserves_directory_with_contents(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    project_id: ProjectID,
    node_id: NodeID,
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
):
    """Directory fmd entries are never removed. S3 objects under them are untouched."""
    dir_file_id = SimcoreS3FileID(f"{project_id}/{node_id}/{generate_password(8)}")

    s3_keys = [
        f"{dir_file_id}/file_at_root.txt",
        f"{dir_file_id}/subdir_a/data.csv",
        f"{dir_file_id}/subdir_a/nested/deep.bin",
        f"{dir_file_id}/subdir_b/image.png",
    ]
    for key in s3_keys:
        await raw_s3_client.put_object(Bucket=storage_s3_bucket, Key=key, Body=b"content")

    await create_fmd_row(file_id=dir_file_id, project_id=project_id, node_id=node_id, is_directory=True)

    removed = await reconcile_db_to_s3(initialized_app, force=True)

    assert removed == 0
    await assert_fmd_row_exists(initialized_app, dir_file_id)
    await assert_s3_keys_exist(raw_s3_client, storage_s3_bucket, s3_keys)


async def test_reconcile_db_to_s3_preserves_empty_directory(
    initialized_app: FastAPI,
    project_id: ProjectID,
    node_id: NodeID,
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
):
    """Empty directory fmd entries are preserved — services may populate them later."""
    dir_file_id = await create_fmd_row(project_id=project_id, node_id=node_id, is_directory=True)

    removed = await reconcile_db_to_s3(initialized_app, force=True)

    assert removed == 0
    await assert_fmd_row_exists(initialized_app, dir_file_id)


async def test_reconcile_db_to_s3_keeps_row_when_s3_object_exists(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    project_id: ProjectID,
    node_id: NodeID,
    create_fmd_row: Callable[..., Awaitable[SimcoreS3FileID]],
):
    """An fmd row with a matching S3 object must NOT be deleted."""
    file_id = await create_fmd_row(project_id=project_id, node_id=node_id)
    await raw_s3_client.put_object(Bucket=storage_s3_bucket, Key=file_id, Body=b"real-data")

    removed = await reconcile_db_to_s3(initialized_app, force=True)

    assert removed == 0
    await assert_fmd_row_exists(initialized_app, file_id)


# ---------------------------------------------------------------------------
# run_reconciliation_passes (top-level runner)
# ---------------------------------------------------------------------------


async def test_run_reconciliation_passes_calls_all_passes(
    initialized_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
):
    """The runner invokes all three passes."""
    called: list[str] = []

    async def _fake_db_to_s3(app, **_kwargs):
        called.append("db_to_s3")
        return 0

    async def _fake_s3_to_db(app, **_kwargs):
        called.append("s3_to_db")
        return 0

    async def _fake_multipart(app, **_kwargs):
        called.append("multipart")
        return 0

    monkeypatch.setattr(recon_mod, "reconcile_db_to_s3", _fake_db_to_s3)
    monkeypatch.setattr(recon_mod, "reconcile_s3_to_db", _fake_s3_to_db)
    monkeypatch.setattr(recon_mod, "reconcile_abandoned_multipart_uploads", _fake_multipart)

    await run_reconciliation_passes(initialized_app)

    assert "db_to_s3" in called
    assert "s3_to_db" in called
    assert "multipart" in called


async def test_run_reconciliation_passes_does_not_raise_on_failure(
    initialized_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
):
    """If one pass raises, the runner logs and continues — never propagates."""
    called: list[str] = []

    async def _exploding_pass(app, **_kwargs):
        msg = "boom"
        raise RuntimeError(msg)

    async def _ok_pass(app, **_kwargs):
        called.append("ok")
        return 0

    monkeypatch.setattr(recon_mod, "reconcile_db_to_s3", _exploding_pass)
    monkeypatch.setattr(recon_mod, "reconcile_s3_to_db", _ok_pass)
    monkeypatch.setattr(recon_mod, "reconcile_abandoned_multipart_uploads", _ok_pass)

    await run_reconciliation_passes(initialized_app)  # must not raise

    assert len(called) == 2  # the other two passes still ran


async def test_reconcile_multipart_handles_no_such_upload(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
):
    """If a multipart upload disappears between list and abort, no crash."""
    orphan_key = f"{uuid4()}/{uuid4()}/vanishing.bin"
    create_resp = await raw_s3_client.create_multipart_upload(Bucket=storage_s3_bucket, Key=orphan_key)
    upload_id = create_resp["UploadId"]

    # Abort it manually so the reconciliation will get NoSuchUpload
    await raw_s3_client.abort_multipart_upload(Bucket=storage_s3_bucket, Key=orphan_key, UploadId=upload_id)

    # Should not raise even though the upload is already gone
    aborted = await reconcile_abandoned_multipart_uploads(initialized_app)
    assert aborted >= 0


async def test_reconcile_multipart_grace_period_protects_recent_uploads(
    initialized_app: FastAPI,
    storage_s3_bucket: str,
    raw_s3_client: S3Client,
    monkeypatch: pytest.MonkeyPatch,
):
    """A non-zero grace period prevents aborting uploads that are still recent."""
    # Override grace period to 1 hour so the just-created upload is protected
    real_settings = initialized_app.state.settings
    stub = real_settings.model_copy(update={"STORAGE_CLEANER_RECONCILE_GRACE_PERIOD": timedelta(hours=1)})
    monkeypatch.setattr(recon_mod, "get_application_settings", lambda _app: stub)

    orphan_key = f"{uuid4()}/{uuid4()}/recent-upload.bin"
    create_resp = await raw_s3_client.create_multipart_upload(Bucket=storage_s3_bucket, Key=orphan_key)
    upload_id = create_resp["UploadId"]

    # The upload was just created — it's younger than the 1h grace period
    aborted = await reconcile_abandoned_multipart_uploads(initialized_app)
    assert aborted == 0

    # Verify the upload is still there
    listing = await raw_s3_client.list_multipart_uploads(Bucket=storage_s3_bucket)
    remaining_ids = {u.get("UploadId") for u in listing.get("Uploads", [])}
    assert upload_id in remaining_ids
