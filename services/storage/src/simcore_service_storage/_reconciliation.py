"""Reconciliation passes for the storage DSM cleaner.

These passes detect and remove three classes of orphans that the normal delete
chain cannot catch — either because they were created before the safer
delete chain landed, or because of races / partial failures in the new chain:

(a) ``reconcile_db_to_s3``: ``file_meta_data`` rows whose referenced S3 object
    no longer exists. Already partially handled by ``_clean_expired_uploads``
    for in-progress uploads; this pass extends it to *completed* entries
    (``upload_expires_at IS NULL``) older than the grace period.

(b) ``reconcile_s3_to_db``: top-level ``<project_id>/`` prefixes in the bucket
    whose ``project_id`` exists neither in the ``projects`` table nor in any
    ``file_meta_data`` row. The whole prefix is wiped recursively.

(c) ``reconcile_abandoned_multipart_uploads``: ongoing multipart uploads on the
    bucket that are older than the grace period AND whose key has no matching
    active fmd row. Aborts them so S3 stops billing for the parts.

All passes are guarded by feature-flag settings and log structured events for
ops observability. They are designed to be safe to run repeatedly.
"""

import asyncio
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

import arrow
import sqlalchemy as sa
from aws_library.s3 import S3DirectoryMetaData
from botocore.exceptions import ClientError
from fastapi import FastAPI
from models_library.projects import ProjectID
from settings_library.redis import RedisDatabase
from settings_library.s3 import S3Settings
from simcore_postgres_database.storage_models import file_meta_data, projects
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from .core.settings import get_application_settings
from .modules.db import get_db_engine
from .modules.redis import get_redis_client_manager
from .modules.s3 import get_s3_client

_logger = logging.getLogger(__name__)


def _get_simcore_bucket_name(app: FastAPI) -> str:
    settings = get_application_settings(app)
    assert settings.STORAGE_S3  # nosec
    s3_settings: S3Settings = settings.STORAGE_S3
    return s3_settings.S3_BUCKET_NAME


def _is_uuid(candidate: str) -> bool:
    try:
        UUID(candidate)
    except (ValueError, AttributeError):
        return False
    return True


def _strip_trailing_slash(prefix: object) -> str:
    s = f"{prefix}"
    return s[:-1] if s.endswith("/") else s


async def _project_ids_with_fmd_rows(app: FastAPI, candidate_ids: Iterable[ProjectID]) -> set[str]:
    """Returns the subset of `candidate_ids` that have at least one fmd row."""
    candidate_str = [f"{pid}" for pid in candidate_ids]
    if not candidate_str:
        return set()
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(
            sa.select(file_meta_data.c.project_id).where(file_meta_data.c.project_id.in_(candidate_str)).distinct()
        )
        return {row[0] for row in rows.fetchall()}


async def _project_ids_existing_in_projects_table(app: FastAPI, candidate_ids: Iterable[ProjectID]) -> set[str]:
    candidate_str = [f"{pid}" for pid in candidate_ids]
    if not candidate_str:
        return set()
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(sa.select(projects.c.uuid).where(projects.c.uuid.in_(candidate_str)))
        return {row[0] for row in rows.fetchall()}


async def reconcile_s3_to_db(app: FastAPI, *, force: bool = False, dry_run: bool = False) -> int:
    """Pass (b): wipe top-level <project_id>/ prefixes that have no DB trace.

    Returns the number of project prefixes removed (or that would be removed in dry_run).
    """
    settings = get_application_settings(app)
    if not force and not settings.STORAGE_CLEANER_RECONCILE_S3_TO_DB_ENABLED:
        return 0

    bucket = _get_simcore_bucket_name(app)
    s3_client = get_s3_client(app)
    removed = 0

    next_cursor = None
    while True:
        entries, next_cursor = await s3_client.list_objects(
            bucket=bucket, prefix=None, start_after=None, next_cursor=next_cursor
        )

        project_id_candidates: list[ProjectID] = []
        for entry in entries:
            if not isinstance(entry, S3DirectoryMetaData):
                continue
            top = _strip_trailing_slash(entry.prefix).split("/", 1)[0]
            if _is_uuid(top):
                project_id_candidates.append(ProjectID(top))

        if project_id_candidates:
            with_db_project = await _project_ids_existing_in_projects_table(app, project_id_candidates)
            with_fmd = await _project_ids_with_fmd_rows(app, project_id_candidates)
            orphan_ids = [
                pid for pid in project_id_candidates if f"{pid}" not in with_db_project and f"{pid}" not in with_fmd
            ]
            for pid in orphan_ids:
                if dry_run:
                    _logger.info("[DRY-RUN] Would remove orphan S3 prefix %s/", pid)
                else:
                    await s3_client.delete_objects_recursively(bucket=bucket, prefix=f"{pid}/")
                removed += 1

        if not next_cursor:
            break

    return removed


async def reconcile_abandoned_multipart_uploads(app: FastAPI, *, force: bool = False, dry_run: bool = False) -> int:
    """Pass (c): abort ongoing multipart uploads with no active fmd row.

    Returns the number of multipart uploads aborted (or that would be aborted in dry_run).
    """
    settings = get_application_settings(app)
    if not force and not settings.STORAGE_CLEANER_RECONCILE_MULTIPART_ENABLED:
        return 0

    bucket = _get_simcore_bucket_name(app)
    s3_client = get_s3_client(app)
    grace_cutoff = datetime.now(tz=UTC) - settings.STORAGE_CLEANER_RECONCILE_GRACE_PERIOD

    ongoing = await s3_client.list_ongoing_multipart_uploads(bucket=bucket)
    if not ongoing:
        return 0

    # Filter by grace period: only consider uploads initiated before the cutoff
    aged_uploads = [
        (upload_id, object_key, initiated) for upload_id, object_key, initiated in ongoing if initiated < grace_cutoff
    ]
    if not aged_uploads:
        return 0

    keys = [object_key for _upload_id, object_key, _initiated in aged_uploads]
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(
            sa.select(file_meta_data.c.file_id).where(
                file_meta_data.c.file_id.in_(keys),
                file_meta_data.c.upload_id.is_not(None),
            )
        )
        keys_with_active_upload = {row[0] for row in rows.fetchall()}

    aborted = 0
    for upload_id, object_key, _initiated in aged_uploads:
        if object_key in keys_with_active_upload:
            continue
        if dry_run:
            _logger.info("[DRY-RUN] Would abort multipart upload %s for key %s", upload_id, object_key)
        else:
            try:
                await s3_client.abort_multipart_upload(bucket=bucket, object_key=object_key, upload_id=upload_id)
            except ClientError as err:
                if err.response.get("Error", {}).get("Code") == "NoSuchUpload":
                    _logger.debug("Upload %s already gone, skipping", upload_id)
                    continue
                raise
        aborted += 1

    return aborted


_CURSOR_REDIS_KEY: str = "storage:reconcile:db_to_s3:cursor"


def _group_eligible_by_project(all_candidates: list, grace_cutoff: datetime) -> dict[str, list[str]]:
    """Group fmd rows by project_id, filtering by grace period.

    Returns {project_id: [file_id, ...]}.
    Only non-directory rows are included — directory entries are never deleted.
    Rows with missing/empty project_id are skipped to avoid full-bucket scans.
    """
    result: dict[str, list[str]] = {}
    for row in all_candidates:
        file_id, project_id, created_at_raw = row[0], row[1], row[2]
        if not project_id:
            _logger.warning("Skipping fmd row %s with NULL/empty project_id", file_id)
            continue
        try:
            created_at = arrow.get(created_at_raw).datetime
        except (arrow.parser.ParserError, ValueError, TypeError):
            created_at = datetime.min.replace(tzinfo=UTC)
        if created_at < grace_cutoff:
            result.setdefault(project_id, []).append(file_id)
    return result


async def _get_cursor(app: FastAPI) -> str:
    """Retrieve the persisted cursor from Redis (empty string = start)."""
    redis = get_redis_client_manager(app).client(RedisDatabase.LOCKS).redis
    value = await redis.get(_CURSOR_REDIS_KEY)
    if value is None:
        return ""
    return value if isinstance(value, str) else value.decode()


async def _set_cursor(app: FastAPI, cursor: str) -> None:
    """Persist the cursor in Redis."""
    redis = get_redis_client_manager(app).client(RedisDatabase.LOCKS).redis
    if cursor:
        await redis.set(_CURSOR_REDIS_KEY, cursor)
    else:
        await redis.delete(_CURSOR_REDIS_KEY)


async def reconcile_db_to_s3(app: FastAPI, *, force: bool = False, dry_run: bool = False) -> int:
    """Pass (a): remove fmd rows whose S3 object is gone.

    Uses cursor-based batching: each invocation processes up to
    ``STORAGE_CLEANER_RECONCILE_BATCH_SIZE`` distinct project_ids, persisting
    the cursor in Redis. When all projects have been processed the cursor
    resets and the next cycle starts from the beginning.

    When ``force=True`` (CLI mode), processes ALL projects in one call
    (ignores cursor/batching).

    Only considers completed entries (``upload_expires_at IS NULL``) older than
    ``STORAGE_CLEANER_RECONCILE_GRACE_PERIOD``. The grace period is critical:
    a long-running direct PUT (or freshly-assembled multipart) creates the fmd
    row BEFORE the S3 object becomes visible, so a naive head check would
    falsely flag in-flight uploads as zombies.

    NOTE: ``file_meta_data.created_at`` is stored as ``varchar`` (legacy ISO
    string), so the cutoff is applied in Python after fetching the rows.

    Returns the number of dangling fmd rows removed (or that would be in dry_run).
    """
    settings = get_application_settings(app)
    if not force and not settings.STORAGE_CLEANER_RECONCILE_DB_TO_S3_ENABLED:
        return 0

    bucket = _get_simcore_bucket_name(app)
    s3_client = get_s3_client(app)
    grace_cutoff = datetime.now(tz=UTC) - settings.STORAGE_CLEANER_RECONCILE_GRACE_PERIOD

    if force:
        # CLI mode: process everything in one shot
        return await _reconcile_db_to_s3_all(app, bucket, s3_client, grace_cutoff, dry_run=dry_run)

    # Background mode: cursor-based batching
    cursor = await _get_cursor(app)
    batch_size = settings.STORAGE_CLEANER_RECONCILE_BATCH_SIZE

    # Fetch next batch of distinct project_ids > cursor
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        query = (
            sa.select(sa.distinct(file_meta_data.c.project_id))
            .where(
                file_meta_data.c.upload_expires_at.is_(None),
                file_meta_data.c.project_id.is_not(None),
                file_meta_data.c.project_id != "",
                file_meta_data.c.project_id > cursor if cursor else sa.true(),
            )
            .order_by(file_meta_data.c.project_id)
            .limit(batch_size)
        )
        rows = await conn.execute(query)
        batch_project_ids: list[str] = [row[0] for row in rows.fetchall()]

    if not batch_project_ids:
        # Cycle complete — reset cursor for next full sweep
        await _set_cursor(app, "")
        return 0

    # Persist cursor for next tick
    await _set_cursor(app, batch_project_ids[-1])

    # Fetch fmd rows for this batch of projects (directories excluded — never deleted)
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(
            sa.select(
                file_meta_data.c.file_id,
                file_meta_data.c.project_id,
                file_meta_data.c.created_at,
            ).where(
                file_meta_data.c.upload_expires_at.is_(None),
                file_meta_data.c.is_directory.is_(False),
                file_meta_data.c.project_id.in_(batch_project_ids),
            )
        )
        all_candidates = rows.fetchall()

    candidates_by_project = _group_eligible_by_project(all_candidates, grace_cutoff)
    return await _delete_dangling_fmd_rows(app, bucket, s3_client, candidates_by_project, dry_run=dry_run)


async def _reconcile_db_to_s3_all(
    app: FastAPI, bucket: str, s3_client, grace_cutoff: datetime, *, dry_run: bool = False
) -> int:
    """Full sweep (used by CLI --force mode)."""
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(
            sa.select(
                file_meta_data.c.file_id,
                file_meta_data.c.project_id,
                file_meta_data.c.created_at,
            ).where(
                file_meta_data.c.upload_expires_at.is_(None),
                file_meta_data.c.is_directory.is_(False),
            )
        )
        all_candidates = rows.fetchall()

    candidates_by_project = _group_eligible_by_project(all_candidates, grace_cutoff)
    return await _delete_dangling_fmd_rows(app, bucket, s3_client, candidates_by_project, dry_run=dry_run)


async def _delete_dangling_fmd_rows(
    app: FastAPI, bucket: str, s3_client, candidates_by_project: dict[str, list[str]], *, dry_run: bool = False
) -> int:
    """For each project, list S3 keys and diff against fmd file_ids.

    Only regular (non-directory) file entries are passed in; directory entries
    are excluded upstream because they must never be deleted by reconciliation.

    An S3 file is considered "covered" if its key matches a regular fmd entry
    OR if it resides under a directory fmd entry's prefix — but this function
    only decides whether a given fmd *row* is dangling (has no backing S3
    object). The S3→DB pass handles orphan S3 objects separately.
    """
    if not candidates_by_project:
        return 0

    sem = asyncio.Semaphore(50)

    async def _find_dangling_for_project(project_id: str, file_ids: list[str]) -> list[str]:
        async with sem:
            s3_keys: set[str] = set()
            prefix = f"{project_id}/" if project_id else ""
            async for page in s3_client.list_objects_paginated(bucket=bucket, prefix=prefix):
                s3_keys.update(obj.object_key for obj in page)
            return [fid for fid in file_ids if fid not in s3_keys]

    results = await asyncio.gather(
        *(_find_dangling_for_project(pid, fids) for pid, fids in candidates_by_project.items())
    )
    dangling_file_ids: list[str] = [fid for batch in results for fid in batch]

    if not dangling_file_ids:
        return 0

    if dry_run:
        for fid in dangling_file_ids:
            _logger.info("[DRY-RUN] Would remove dangling fmd row %s", fid)
    else:
        async with get_db_engine(app).begin() as conn:
            await conn.execute(file_meta_data.delete().where(file_meta_data.c.file_id.in_(dangling_file_ids)))

    return len(dangling_file_ids)


async def run_reconciliation_passes(app: FastAPI) -> None:
    """Run all enabled reconciliation passes; never raises (logs only)."""
    for fn in (
        reconcile_db_to_s3,
        reconcile_s3_to_db,
        reconcile_abandoned_multipart_uploads,
    ):
        try:
            await fn(app)
        except Exception:  # pylint: disable=broad-except
            _logger.exception("reconciliation pass %s failed", fn.__name__)
