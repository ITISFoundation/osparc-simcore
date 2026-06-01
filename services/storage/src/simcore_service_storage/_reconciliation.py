"""Reconciliation passes for the storage DSM cleaner.

These passes detect and remove four classes of orphans that the normal delete
chain cannot catch — either because they were created before the safer
delete chain landed, or because of races / partial failures in the new chain:

(a) ``reconcile_db_to_s3``: ``file_meta_data`` rows whose referenced S3 object
    no longer exists. Already partially handled by ``_clean_expired_uploads``
    for in-progress uploads; this pass extends it to *completed* entries
    (``upload_expires_at IS NULL``) older than the grace period. Also covers
    ``exports/`` fmd rows whose S3 object was removed by the bucket lifecycle
    policy.

(b) ``reconcile_s3_to_db``: top-level ``<project_id>/`` prefixes in the bucket
    whose ``project_id`` exists neither in the ``projects`` table nor in any
    ``file_meta_data`` row. The whole prefix is wiped recursively. Also scans
    the ``api/`` prefix for S3 objects that have no matching fmd row.

(c) ``reconcile_abandoned_multipart_uploads``: ongoing multipart uploads on the
    bucket that are older than the grace period AND whose key has no matching
    active fmd row. Aborts them so S3 stops billing for the parts.

(d) ``reconcile_orphaned_api_files``: user-uploaded ``api/`` files
    (``project_id IS NULL``, ``is_soft_link IS FALSE``) that are no longer
    referenced as ``SimCoreFileLink`` inputs/outputs in any project workbench.
    Uses a two-phase Redis-cached scan so the work is spread across many
    cleaner ticks without overwhelming the DB. A 30-day age gate ensures no
    false positives even when the scan takes days to complete.

All passes are guarded by feature-flag settings and log structured events for
ops observability. They are designed to be safe to run repeatedly.
"""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime

import arrow
import redis.asyncio as aioredis
import sqlalchemy as sa
from aws_library.s3 import S3DirectoryMetaData, S3MetaData, S3UploadNotFoundError, SimcoreS3API
from fastapi import FastAPI
from models_library.projects import ProjectID
from servicelib.utils import limited_gather
from settings_library.redis import RedisDatabase
from settings_library.s3 import S3Settings
from simcore_postgres_database.storage_models import file_meta_data, projects
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from .core.settings import ApplicationSettings, get_application_settings
from .models import is_uuid
from .modules.db import get_db_engine
from .modules.redis import get_redis_client_manager
from .modules.s3 import get_s3_client

_logger = logging.getLogger(__name__)


def _get_simcore_bucket_name(app: FastAPI) -> str:
    settings = get_application_settings(app)
    assert settings.STORAGE_S3  # nosec
    s3_settings: S3Settings = settings.STORAGE_S3
    return s3_settings.S3_BUCKET_NAME


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

    Also scans the ``api/`` prefix for S3 objects that have no matching fmd row
    (Phase 3 — S3 objects created by partial upload failures or manual fmd deletions).

    Returns the number of project prefixes removed plus orphan api/ S3 objects deleted
    (or that would be removed in dry_run).
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
            top = f"{entry.prefix}".removesuffix("/").split("/", 1)[0]
            if is_uuid(top):
                project_id_candidates.append(ProjectID(top))

        if project_id_candidates:
            with_db_project = await _project_ids_existing_in_projects_table(app, project_id_candidates)
            with_fmd = await _project_ids_with_fmd_rows(app, project_id_candidates)
            orphans_project_ids = [
                p for p in project_id_candidates if f"{p}" not in with_db_project and f"{p}" not in with_fmd
            ]
            for project_id in orphans_project_ids:
                if dry_run:
                    _logger.info("[DRY-RUN] Would remove orphan S3 prefix %s/", project_id)
                else:
                    await s3_client.delete_objects_recursively(bucket=bucket, prefix=f"{project_id}/")
                    _logger.info("Removed orphan S3 prefix %s/ (no project or fmd rows)", project_id)
                removed += 1

        if not next_cursor:
            break

    # Phase 3: scan api/ prefix for S3 objects with no fmd row
    removed += await _reconcile_api_s3_orphans(app, bucket, s3_client, settings, dry_run=dry_run)

    return removed


async def _reconcile_api_s3_orphans(
    app: FastAPI,
    bucket: str,
    s3_client: SimcoreS3API,
    settings: ApplicationSettings,
    *,
    dry_run: bool = False,
) -> int:
    """Scan api/ prefix for S3 objects that have no file_meta_data row.

    Uses ``list_objects_paginated`` (no delimiter — recursive listing) so
    individual objects inside ``api/{uuid}/`` sub-prefixes are enumerated.
    PK-range batch lookups avoid full table scans. Only objects older than
    ``STORAGE_CLEANER_RECONCILE_GRACE_PERIOD`` are considered.
    """
    grace_cutoff = datetime.now(tz=UTC) - settings.STORAGE_CLEANER_RECONCILE_GRACE_PERIOD
    deleted = 0

    async for page in s3_client.list_objects_paginated(bucket=bucket, prefix="api/"):
        deleted += await _process_api_s3_page(app, bucket, s3_client, page, grace_cutoff, dry_run=dry_run)

    return deleted


async def _process_api_s3_page(
    app: FastAPI,
    bucket: str,
    s3_client: SimcoreS3API,
    page: list[S3MetaData],
    grace_cutoff: datetime,
    *,
    dry_run: bool,
) -> int:
    """Process one page of S3MetaData objects from list_objects_paginated."""
    object_keys = [str(obj.object_key) for obj in page]
    last_modified_by_key: dict[str, datetime] = {str(obj.object_key): obj.last_modified for obj in page}

    if not object_keys:
        return 0

    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(sa.select(file_meta_data.c.file_id).where(file_meta_data.c.file_id.in_(object_keys)))
        known_keys: set[str] = {row[0] for row in rows.fetchall()}

    deleted = 0
    for key in object_keys:
        if key in known_keys:
            continue
        last_mod = last_modified_by_key.get(key)
        if last_mod and last_mod.replace(tzinfo=UTC) > grace_cutoff:
            continue
        if dry_run:
            _logger.info("[DRY-RUN] Would remove orphan api/ S3 object %s (no fmd row)", key)
        else:
            await s3_client.delete_objects_recursively(bucket=bucket, prefix=key)
            _logger.info("Removed orphan api/ S3 object %s (no fmd row)", key)
        deleted += 1
    return deleted


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
        keys_with_active_upload: set[str] = {row[0] for row in rows.fetchall()}

    aborted = 0
    for upload_id, object_key, _initiated in aged_uploads:
        if object_key in keys_with_active_upload:
            continue
        if dry_run:
            _logger.info("[DRY-RUN] Would abort multipart upload %s for key %s", upload_id, object_key)
        else:
            try:
                await s3_client.abort_multipart_upload(bucket=bucket, object_key=object_key, upload_id=upload_id)
                _logger.info("Aborted abandoned multipart upload %s for key %s", upload_id, object_key)
            except S3UploadNotFoundError:
                _logger.debug("Upload %s already gone, skipping", upload_id)
                continue
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

    Also cleans ``exports/`` fmd rows whose S3 object was removed by the bucket
    lifecycle policy (Phase 1). These rows have ``project_id IS NULL`` and are
    scanned via PK range to avoid unindexed column filters.

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
        removed = await _reconcile_db_to_s3_all(app, bucket, s3_client, grace_cutoff, dry_run=dry_run)
        removed += await _reconcile_exports_fmd_all(app, bucket, s3_client, grace_cutoff, dry_run=dry_run)
        return removed

    # Background mode: cursor-based batching for project files
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
        # Also process one batch of exports/ fmd rows each time the project cycle completes
        return await _reconcile_exports_fmd_batch(app, bucket, s3_client, grace_cutoff, dry_run=dry_run)

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
    app: FastAPI, bucket: str, s3_client: SimcoreS3API, grace_cutoff: datetime, *, dry_run: bool = False
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


# ---------------------------------------------------------------------------
# Phase 1: exports/ fmd row cleanup
# ---------------------------------------------------------------------------

_EXPORTS_FMD_CURSOR_REDIS_KEY: str = "storage:reconcile:db_to_s3:exports_cursor"
# PK upper bound for the exports/ prefix. "exports0" > any "exports/..." string because
# ord('0') == 48 > ord('/') == 47, so this reliably terminates the range scan.
_EXPORTS_PK_UPPER_BOUND: str = "exports0"
_EXPORTS_FMD_BATCH_SIZE: int = 500
# Maximum concurrent S3 HEAD requests when checking object existence.
_S3_OBJECT_EXISTS_CONCURRENCY: int = 5


async def _process_exports_fmd_page(
    app: FastAPI,
    bucket: str,
    s3_client: SimcoreS3API,
    grace_cutoff: datetime,
    cursor: str,
    *,
    dry_run: bool,
) -> tuple[int, str | None]:
    """Fetch one page of exports/ fmd rows, check S3, delete dangling rows.

    Returns ``(n_deleted, next_cursor)`` where ``next_cursor`` is ``None`` when
    the batch was empty (all rows exhausted — caller should reset its cursor).
    """
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(
            sa.select(file_meta_data.c.file_id, file_meta_data.c.upload_expires_at, file_meta_data.c.created_at)
            .where(
                file_meta_data.c.file_id > cursor,
                file_meta_data.c.file_id < _EXPORTS_PK_UPPER_BOUND,
            )
            .order_by(file_meta_data.c.file_id)
            .limit(_EXPORTS_FMD_BATCH_SIZE)
        )
        batch = rows.fetchall()

    if not batch:
        return 0, None

    next_cursor = f"{batch[-1][0]}"

    # Filter eligible candidates in Python (avoids unindexed column predicates in SQL)
    candidates = [
        file_id
        for file_id, upload_expires_at, created_at_raw in batch
        if upload_expires_at is None and _parse_created_at(created_at_raw) < grace_cutoff
    ]
    if not candidates:
        return 0, next_cursor

    # Check S3 existence in parallel — each call is an independent HEAD request
    exists_results: list[bool] = await limited_gather(
        *(s3_client.object_exists(bucket=bucket, object_key=fid) for fid in candidates),
        limit=_S3_OBJECT_EXISTS_CONCURRENCY,
        reraise=True,
    )
    dangling = [fid for fid, exists in zip(candidates, exists_results, strict=True) if not exists]
    if not dangling:
        return 0, next_cursor

    if dry_run:
        for fid in dangling:
            _logger.info("[DRY-RUN] Would remove dangling exports/ fmd row %s (S3 object gone)", fid)
    else:
        async with get_db_engine(app).begin() as conn:
            await conn.execute(file_meta_data.delete().where(file_meta_data.c.file_id.in_(dangling)))
        _logger.info("Removed %d dangling exports/ fmd rows whose S3 objects were gone: %s", len(dangling), dangling)

    return len(dangling), next_cursor


async def _reconcile_exports_fmd_batch(
    app: FastAPI, bucket: str, s3_client: SimcoreS3API, grace_cutoff: datetime, *, dry_run: bool = False
) -> int:
    """Process one batch of exports/ fmd rows — check S3 and delete dangling rows.

    Uses a Redis cursor to paginate through the exports/ PK range across ticks.
    """
    redis = get_redis_client_manager(app).client(RedisDatabase.LOCKS).redis
    raw = await redis.get(_EXPORTS_FMD_CURSOR_REDIS_KEY)
    cursor = (raw.decode() if isinstance(raw, bytes) else raw) or "exports/"

    n_deleted, next_cursor = await _process_exports_fmd_page(
        app, bucket, s3_client, grace_cutoff, cursor, dry_run=dry_run
    )
    if next_cursor is None:
        await redis.delete(_EXPORTS_FMD_CURSOR_REDIS_KEY)  # cycle complete — reset
    else:
        await redis.set(_EXPORTS_FMD_CURSOR_REDIS_KEY, next_cursor)
    return n_deleted


async def _reconcile_exports_fmd_all(
    app: FastAPI, bucket: str, s3_client: SimcoreS3API, grace_cutoff: datetime, *, dry_run: bool = False
) -> int:
    """Full sweep of exports/ fmd rows (CLI --force mode)."""
    total = 0
    cursor = "exports/"
    while True:
        n_deleted, next_cursor = await _process_exports_fmd_page(
            app, bucket, s3_client, grace_cutoff, cursor, dry_run=dry_run
        )
        total += n_deleted
        if next_cursor is None:
            break
        cursor = next_cursor
    return total


def _parse_created_at(created_at_raw: str | None) -> datetime:
    try:
        return arrow.get(created_at_raw or "").datetime
    except (arrow.parser.ParserError, ValueError, TypeError):
        return datetime.min.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# Phase 2 (Pass d): reconcile orphaned api/ user-upload files
# ---------------------------------------------------------------------------

_API_ORPHAN_REFERENCED_KEY: str = "storage:reconcile:api:referenced_paths"
_API_ORPHAN_CANDIDATES_KEY: str = "storage:reconcile:api:candidates"
_API_ORPHAN_PROJECT_CURSOR_KEY: str = "storage:reconcile:api:project_cursor"
_API_ORPHAN_FMD_CURSOR_KEY: str = "storage:reconcile:api:fmd_cursor"
_API_ORPHAN_SCAN_STARTED_AT_KEY: str = "storage:reconcile:api:scan_started_at"
_API_ORPHAN_PROJECT_SCAN_COMPLETE_KEY: str = "storage:reconcile:api:project_scan_complete"
_API_ORPHAN_FMD_SCAN_COMPLETE_KEY: str = "storage:reconcile:api:fmd_scan_complete"

# PK upper bound for the api/ range. "api0" > any "api/..." string (ord('0')==48 > ord('/')==47).
_API_PK_UPPER_BOUND: str = "api0"
_API_FMD_BATCH_SIZE: int = 500


def _extract_api_paths_from_workbench(workbench: dict) -> set[str]:
    """Return every SimCoreFileLink path starting with 'api/' from a workbench dict."""
    paths: set[str] = set()
    for node_data in workbench.values():
        if not isinstance(node_data, dict):
            continue
        for port_dict in (node_data.get("inputs") or {}, node_data.get("outputs") or {}):
            if not isinstance(port_dict, dict):
                continue
            for val in port_dict.values():
                if isinstance(val, dict) and val.get("store") == 0:
                    path = val.get("path", "")
                    if isinstance(path, str) and path.startswith("api/"):
                        paths.add(path)
    return paths


async def _api_orphan_reset_redis(redis: aioredis.Redis) -> None:
    await redis.delete(
        _API_ORPHAN_REFERENCED_KEY,
        _API_ORPHAN_CANDIDATES_KEY,
        _API_ORPHAN_PROJECT_CURSOR_KEY,
        _API_ORPHAN_FMD_CURSOR_KEY,
        _API_ORPHAN_SCAN_STARTED_AT_KEY,
        _API_ORPHAN_PROJECT_SCAN_COMPLETE_KEY,
        _API_ORPHAN_FMD_SCAN_COMPLETE_KEY,
    )


async def _fetch_project_workbench_page(
    app: FastAPI,
    cursor: str,
    limit: int,
) -> tuple[list, str | None]:
    """Fetch one page of (uuid, workbench) rows from the projects table.

    Returns ``(batch, next_cursor)`` where ``next_cursor`` is ``None`` when exhausted.
    """
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(
            sa.select(projects.c.uuid, projects.c.workbench)
            .where(projects.c.uuid > cursor if cursor else sa.true())
            .order_by(projects.c.uuid)
            .limit(limit)
        )
        batch = rows.fetchall()
    if not batch:
        return [], None
    return batch, f"{batch[-1][0]}"


async def _fetch_api_fmd_candidates_page(
    app: FastAPI,
    cursor: str,
    grace_cutoff: datetime,
    limit: int,
) -> tuple[list[str], str | None]:
    """Fetch one page of eligible api/ fmd file_ids (project_id NULL, not soft link, completed, old enough).

    Returns ``(candidate_file_ids, next_cursor)`` where ``next_cursor`` is ``None`` when exhausted.
    The cursor advances by the last raw PK seen, regardless of how many rows pass the filter.
    """
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(
            sa.select(
                file_meta_data.c.file_id,
                file_meta_data.c.project_id,
                file_meta_data.c.is_soft_link,
                file_meta_data.c.upload_expires_at,
                file_meta_data.c.created_at,
            )
            .where(
                file_meta_data.c.file_id > cursor,
                file_meta_data.c.file_id < _API_PK_UPPER_BOUND,
            )
            .order_by(file_meta_data.c.file_id)
            .limit(limit)
        )
        batch = rows.fetchall()
    if not batch:
        return [], None
    candidates = [
        file_id
        for file_id, project_id, is_soft_link, upload_expires_at, created_at_raw in batch
        if (
            project_id is None
            and not is_soft_link
            and upload_expires_at is None
            and _parse_created_at(created_at_raw) < grace_cutoff
        )
    ]
    return candidates, f"{batch[-1][0]}"


async def _api_orphan_phase_a_tick(app: FastAPI, redis: aioredis.Redis, batch_size: int) -> bool:
    """Scan one batch of projects and SADD referenced api/ paths.  Returns True when done."""
    raw = await redis.get(_API_ORPHAN_PROJECT_CURSOR_KEY)
    cursor = (raw.decode() if isinstance(raw, bytes) else raw) or ""

    batch, next_cursor = await _fetch_project_workbench_page(app, cursor, batch_size)
    if next_cursor is None:
        await redis.set(_API_ORPHAN_PROJECT_SCAN_COMPLETE_KEY, "1")
        return True

    pipe = redis.pipeline()
    for _uuid, workbench in batch:
        for path in _extract_api_paths_from_workbench(workbench or {}):
            pipe.sadd(_API_ORPHAN_REFERENCED_KEY, path)
    await pipe.execute()
    await redis.set(_API_ORPHAN_PROJECT_CURSOR_KEY, next_cursor)
    return False


async def _api_orphan_phase_a_prime_tick(app: FastAPI, redis: aioredis.Redis, grace_cutoff: datetime) -> bool:
    """Scan one batch of api/ fmd rows and SADD eligible candidates.  Returns True when done."""
    raw = await redis.get(_API_ORPHAN_FMD_CURSOR_KEY)
    cursor = (raw.decode() if isinstance(raw, bytes) else raw) or "api/"

    candidates, next_cursor = await _fetch_api_fmd_candidates_page(app, cursor, grace_cutoff, _API_FMD_BATCH_SIZE)
    if next_cursor is None:
        await redis.set(_API_ORPHAN_FMD_SCAN_COMPLETE_KEY, "1")
        return True

    if candidates:
        pipe = redis.pipeline()
        for file_id in candidates:
            pipe.sadd(_API_ORPHAN_CANDIDATES_KEY, file_id)
        await pipe.execute()
    await redis.set(_API_ORPHAN_FMD_CURSOR_KEY, next_cursor)
    return False


async def _api_orphan_phase_b(
    app: FastAPI, redis: aioredis.Redis, bucket: str, s3_client: SimcoreS3API, *, dry_run: bool = False
) -> int:
    """Compute orphans (candidates - referenced) and delete them; reset Redis state."""
    orphan_raw: set[bytes | str] = await redis.sdiff(  # type: ignore[assignment]
        [_API_ORPHAN_CANDIDATES_KEY, _API_ORPHAN_REFERENCED_KEY]
    )
    orphan_ids: list[str] = [fid.decode() if isinstance(fid, bytes) else str(fid) for fid in orphan_raw]

    deleted = 0
    for file_id in orphan_ids:
        if dry_run:
            _logger.info("[DRY-RUN] Would remove orphaned api/ file %s (no project reference)", file_id)
        else:
            await s3_client.delete_object(bucket=bucket, object_key=file_id)
            async with get_db_engine(app).begin() as conn:
                await conn.execute(file_meta_data.delete().where(file_meta_data.c.file_id == file_id))
            _logger.info("Removed orphaned api/ file %s (no project workbench reference)", file_id)
        deleted += 1

    if orphan_ids:
        _logger.info("api/ orphan pass complete: %d files removed", deleted)

    await _api_orphan_reset_redis(redis)
    return deleted


async def reconcile_orphaned_api_files(app: FastAPI, *, force: bool = False, dry_run: bool = False) -> int:
    """Pass (d): detect and remove user-uploaded api/ files no longer referenced by any project.

    Uses a two-phase Redis-cached approach spread across cleaner ticks:

    Phase A  — incrementally scans all project workbenches to build a Redis SET of
               every api/ path still referenced as a SimCoreFileLink input/output.
    Phase A' — incrementally scans fmd rows in the api/ PK range to build a Redis SET
               of candidate file_ids (project_id IS NULL, is_soft_link IS FALSE, old enough).
    Phase B  — computes ``SDIFF candidates referenced`` and deletes the orphans (fmd + S3).

    The ``STORAGE_CLEANER_RECONCILE_API_GRACE_PERIOD`` age gate (default 30 days) ensures
    no false positives: only files whose fmd row is older than the grace period *before*
    the scan started are eligible, so a file created mid-scan is always protected.

    When ``force=True`` (CLI mode) all phases run in a single call.
    """
    settings = get_application_settings(app)
    if not force and not settings.STORAGE_CLEANER_RECONCILE_API_ORPHANS_ENABLED:
        return 0

    redis = get_redis_client_manager(app).client(RedisDatabase.LOCKS).redis
    bucket = _get_simcore_bucket_name(app)
    s3_client = get_s3_client(app)

    if force:
        return await _reconcile_orphaned_api_files_full(app, redis, bucket, s3_client, settings, dry_run=dry_run)

    # Ensure scan_started_at is initialised for this cycle
    started_raw = await redis.get(_API_ORPHAN_SCAN_STARTED_AT_KEY)
    if started_raw is None:
        scan_started_at = datetime.now(tz=UTC)
        await redis.set(_API_ORPHAN_SCAN_STARTED_AT_KEY, scan_started_at.isoformat())
    else:
        started_str = started_raw.decode() if isinstance(started_raw, bytes) else started_raw
        scan_started_at = datetime.fromisoformat(started_str)

    grace_cutoff = scan_started_at - settings.STORAGE_CLEANER_RECONCILE_API_GRACE_PERIOD

    project_done = bool(await redis.get(_API_ORPHAN_PROJECT_SCAN_COMPLETE_KEY))
    fmd_done = bool(await redis.get(_API_ORPHAN_FMD_SCAN_COMPLETE_KEY))

    if project_done and fmd_done:
        return await _api_orphan_phase_b(app, redis, bucket, s3_client, dry_run=dry_run)

    # Advance each incomplete phase by one tick
    if not project_done:
        await _api_orphan_phase_a_tick(app, redis, settings.STORAGE_CLEANER_RECONCILE_API_SCAN_BATCH_SIZE)
    if not fmd_done:
        await _api_orphan_phase_a_prime_tick(app, redis, grace_cutoff)

    return 0


async def _reconcile_orphaned_api_files_full(
    app: FastAPI,
    redis: aioredis.Redis,
    bucket: str,
    s3_client: SimcoreS3API,
    settings: ApplicationSettings,
    *,
    dry_run: bool = False,
) -> int:
    """Full single-shot sweep used by CLI --force mode."""
    grace_cutoff = datetime.now(tz=UTC) - settings.STORAGE_CLEANER_RECONCILE_API_GRACE_PERIOD
    referenced_paths = await _collect_all_referenced_api_paths(app, settings)
    candidate_ids = await _collect_all_api_fmd_candidates(app, grace_cutoff)
    orphan_ids = candidate_ids - referenced_paths
    deleted = await _delete_orphan_api_ids(app, bucket, s3_client, orphan_ids, dry_run=dry_run)
    await _api_orphan_reset_redis(redis)
    return deleted


async def _collect_all_referenced_api_paths(app: FastAPI, settings: ApplicationSettings) -> set[str]:
    referenced_paths: set[str] = set()
    cursor = ""
    while True:
        batch, next_cursor = await _fetch_project_workbench_page(
            app, cursor, settings.STORAGE_CLEANER_RECONCILE_API_SCAN_BATCH_SIZE
        )
        if next_cursor is None:
            break
        for _uuid, workbench in batch:
            referenced_paths.update(_extract_api_paths_from_workbench(workbench or {}))
        cursor = next_cursor
    return referenced_paths


async def _collect_all_api_fmd_candidates(app: FastAPI, grace_cutoff: datetime) -> set[str]:
    candidate_ids: set[str] = set()
    cursor = "api/"
    while True:
        candidates, next_cursor = await _fetch_api_fmd_candidates_page(app, cursor, grace_cutoff, _API_FMD_BATCH_SIZE)
        if next_cursor is None:
            break
        candidate_ids.update(candidates)
        cursor = next_cursor
    return candidate_ids


async def _delete_orphan_api_ids(
    app: FastAPI, bucket: str, s3_client: SimcoreS3API, orphan_ids: set[str], *, dry_run: bool
) -> int:
    deleted = 0
    for file_id in orphan_ids:
        if dry_run:
            _logger.info("[DRY-RUN] Would remove orphaned api/ file %s", file_id)
        else:
            await s3_client.delete_object(bucket=bucket, object_key=file_id)
            async with get_db_engine(app).begin() as conn:
                await conn.execute(file_meta_data.delete().where(file_meta_data.c.file_id == file_id))
            _logger.info("Removed orphaned api/ file %s (no project workbench reference)", file_id)
        deleted += 1
    return deleted


async def _delete_dangling_fmd_rows(
    app: FastAPI,
    bucket: str,
    s3_client: SimcoreS3API,
    candidates_by_project: dict[str, list[str]],
    *,
    dry_run: bool = False,
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

    async def _find_dangling_for_project(project_id: str, file_ids: list[str]) -> list[str]:
        s3_keys: set[str] = set()
        prefix = f"{project_id}/" if project_id else ""
        async for page in s3_client.list_objects_paginated(bucket=bucket, prefix=prefix):
            s3_keys.update(obj.object_key for obj in page)
        return [fid for fid in file_ids if fid not in s3_keys]

    results = await limited_gather(
        *(_find_dangling_for_project(pid, fids) for pid, fids in candidates_by_project.items()),
        reraise=True,
        limit=50,
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
        _logger.info(
            "Removed %d dangling fmd rows with no backing S3 object: %s", len(dangling_file_ids), dangling_file_ids
        )

    return len(dangling_file_ids)


async def run_reconciliation_passes(app: FastAPI) -> None:
    """Run all enabled reconciliation passes; never raises (logs only)."""
    for fn in (
        reconcile_db_to_s3,
        reconcile_s3_to_db,
        reconcile_abandoned_multipart_uploads,
        reconcile_orphaned_api_files,
    ):
        try:
            await fn(app)
        except Exception:  # pylint: disable=broad-except
            _logger.exception("reconciliation pass %s failed", fn.__name__)
