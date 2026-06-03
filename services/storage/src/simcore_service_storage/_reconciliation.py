"""Keeps storage metadata and object storage in sync over time.

This module runs a periodic cleanup pass that removes stale file entries,
cleans up records that point to missing objects, and deletes orphaned project
folders that no longer exist in the database. The workflow is designed to run
continuously in small steps, so it can pause and resume safely across service
restarts without losing progress. For one-off maintenance, it can also execute
as a full sweep in a single run.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import arrow
import sqlalchemy as sa
from aws_library.s3 import S3DirectoryMetaData, SimcoreS3API
from fastapi import FastAPI
from models_library.projects import ProjectID
from servicelib.utils import limited_gather
from settings_library.redis import RedisDatabase
from settings_library.s3 import S3Settings
from simcore_postgres_database.storage_models import file_meta_data, projects
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from .constants import EXPORTS_S3_PREFIX
from .core.settings import get_application_settings
from .models import is_uuid
from .modules.db import get_db_engine
from .modules.redis import get_redis_client_manager
from .modules.s3 import get_s3_client

_logger = logging.getLogger(__name__)


_RECONCILE_CURSOR_KEY = "storage:reconcile:v2:cursor"
_RECONCILE_SCAN_STARTED_AT_KEY = "storage:reconcile:v2:scan_started_at"
_RECONCILE_LIVE_PROJECTS_KEY = "storage:reconcile:v2:live_projects"
_RECONCILE_REFERENCED_PATHS_KEY = "storage:reconcile:v2:referenced_paths"
_RECONCILE_TICK_GATE_KEY = "storage:reconcile:v2:tick_gate"
_S3_EXISTENCE_PROBE_CONCURRENCY = 20


@dataclass(slots=True)
class ReconciliationCounts:
    unreachable_removed: int = 0
    dangling_removed: int = 0
    orphan_prefixes_removed: int = 0

    @property
    def total_removed(self) -> int:
        return self.unreachable_removed + self.dangling_removed + self.orphan_prefixes_removed


@dataclass(slots=True)
class _FmdRow:
    file_id: str
    project_id: str | None
    created_at: datetime
    upload_expires_at: datetime | None
    is_directory: bool


@dataclass(slots=True)
class _PassSnapshot:
    started_at: datetime
    live_projects: set[str]
    referenced_paths: set[str]


# Public API
async def run_reconciliation_pass(app: FastAPI, *, force: bool = False, dry_run: bool = False) -> ReconciliationCounts:
    """Runs one reconciliation tick or a full one-shot pass.

    In background mode, this executes one incremental cursor batch.
    In ``force`` mode (CLI), this executes a full in-process sweep.
    """
    settings = get_application_settings(app)
    if not force and not settings.STORAGE_CLEANER_RECONCILE_ENABLED:
        return ReconciliationCounts()

    bucket = _get_simcore_bucket_name(app)
    s3_client = get_s3_client(app)

    if force:
        snapshot = await _build_snapshot(app)
        cutoff = snapshot.started_at - settings.STORAGE_CLEANER_RECONCILE_GRACE_PERIOD
        counts = await _run_full_sweep(app, bucket, s3_client, snapshot, cutoff, dry_run=dry_run)
        _log_reconcile_summary(counts, dry_run=dry_run, mode="full")
        return counts

    redis = get_redis_client_manager(app).client(RedisDatabase.LOCKS).redis
    snapshot = await _ensure_incremental_snapshot(app, redis)
    cutoff = snapshot.started_at - settings.STORAGE_CLEANER_RECONCILE_GRACE_PERIOD

    counts = await _run_incremental_tick(
        app,
        redis,
        bucket,
        s3_client,
        snapshot,
        cutoff,
        settings.STORAGE_CLEANER_RECONCILE_SCAN_BATCH_SIZE,
        dry_run=dry_run,
    )
    if counts.total_removed:
        _log_reconcile_summary(counts, dry_run=dry_run, mode="tick")
    return counts


async def run_reconciliation_passes(app: FastAPI) -> None:
    """Entry-point used by the DSM cleaner.

    Uses a Redis gate key so reconciliation cadence can be slower than the
    upload-expiry cleaner cadence.
    """
    settings = get_application_settings(app)
    if not settings.STORAGE_CLEANER_RECONCILE_ENABLED:
        return

    redis = get_redis_client_manager(app).client(RedisDatabase.LOCKS).redis
    can_run = await redis.set(
        _RECONCILE_TICK_GATE_KEY,
        datetime.now(tz=UTC).isoformat(),
        ex=int(settings.STORAGE_CLEANER_RECONCILE_INTERVAL.total_seconds()),
        nx=True,
    )
    if not can_run:
        return

    try:
        await run_reconciliation_pass(app, dry_run=False)
    except Exception:  # pylint: disable=broad-except
        _logger.exception("reconciliation v2 tick failed")


# Reconciliation logic
async def _run_incremental_tick(
    app: FastAPI,
    redis: Any,
    bucket: str,
    s3_client: SimcoreS3API,
    snapshot: _PassSnapshot,
    cutoff: datetime,
    batch_size: int,
    *,
    dry_run: bool,
) -> ReconciliationCounts:
    """Process one cursor batch for the active logical pass.

    When no batch is left, this tick performs the wrap-stage cleanup
    (top-level orphan project prefixes) and resets pass state.
    """
    cursor = await _get_cursor(redis)
    batch = await _fetch_fmd_batch(app, cursor, batch_size)

    if not batch:
        prefixes_removed = await _cleanup_orphan_project_prefixes(
            app,
            bucket,
            s3_client,
            snapshot.live_projects,
            dry_run=dry_run,
        )
        await _reset_pass_state(redis)
        return ReconciliationCounts(orphan_prefixes_removed=prefixes_removed)

    counts = await _process_fmd_rows(app, bucket, s3_client, batch, snapshot, cutoff, dry_run=dry_run)
    await _set_cursor(redis, batch[-1].file_id)
    return counts


async def _run_full_sweep(
    app: FastAPI,
    bucket: str,
    s3_client: SimcoreS3API,
    snapshot: _PassSnapshot,
    cutoff: datetime,
    *,
    dry_run: bool,
) -> ReconciliationCounts:
    cursor = ""
    counts = ReconciliationCounts()

    while True:
        batch = await _fetch_fmd_batch(app, cursor, 5000)
        if not batch:
            break

        batch_counts = await _process_fmd_rows(app, bucket, s3_client, batch, snapshot, cutoff, dry_run=dry_run)
        counts.unreachable_removed += batch_counts.unreachable_removed
        counts.dangling_removed += batch_counts.dangling_removed
        cursor = batch[-1].file_id

    counts.orphan_prefixes_removed = await _cleanup_orphan_project_prefixes(
        app,
        bucket,
        s3_client,
        snapshot.live_projects,
        dry_run=dry_run,
    )
    return counts


async def _process_fmd_rows(
    app: FastAPI,
    bucket: str,
    s3_client: SimcoreS3API,
    rows: list[_FmdRow],
    snapshot: _PassSnapshot,
    cutoff: datetime,
    *,
    dry_run: bool,
) -> ReconciliationCounts:
    """Apply row-level GC rules for one fmd batch.

    Rule 1 (reachability): delete old, unreachable non-exports rows (S3 + fmd).
    Rule 2 (dangling): for old reachable rows and old exports rows, probe S3
    existence and delete only dangling fmd rows.

    Directories are never S3-probed for dangling checks.
    """
    counts = ReconciliationCounts()
    probe_candidates: list[str] = []

    for row in rows:
        if row.upload_expires_at is not None or row.created_at >= cutoff:
            continue

        is_exports = _is_exports_row(row.file_id)
        reachable = _is_reachable(row, snapshot)

        if not is_exports and not reachable:
            await _remove_unreachable_row(app, bucket, s3_client, row, dry_run=dry_run)
            counts.unreachable_removed += 1
            continue

        if not row.is_directory and (reachable or is_exports):
            probe_candidates.append(row.file_id)

    if not probe_candidates:
        return counts

    exists_results: list[bool] = await limited_gather(
        *(s3_client.object_exists(bucket=bucket, object_key=file_id) for file_id in probe_candidates),
        reraise=True,
        limit=_S3_EXISTENCE_PROBE_CONCURRENCY,
    )
    missing = [file_id for file_id, exists in zip(probe_candidates, exists_results, strict=True) if not exists]
    if not missing:
        return counts

    if dry_run:
        for file_id in missing:
            _logger.info("[DRY-RUN] Would remove dangling fmd row %s", file_id)
    else:
        await _delete_fmd_rows(app, missing)

    counts.dangling_removed += len(missing)
    return counts


async def _cleanup_orphan_project_prefixes(
    app: FastAPI,
    bucket: str,
    s3_client: SimcoreS3API,
    live_projects: set[str],
    *,
    dry_run: bool,
) -> int:
    """Delete top-level ``<uuid>/`` prefixes that have no DB trace.

    This stage intentionally uses top-level S3 listing only. Non-UUID top-level
    prefixes (for example api/ or exports/) are skipped by design.
    """
    removed = 0
    next_cursor: str | None = None

    while True:
        entries, next_cursor = await s3_client.list_objects(
            bucket=bucket,
            prefix=None,
            start_after=None,
            next_cursor=next_cursor,
        )

        project_candidates: list[ProjectID] = []
        for entry in entries:
            if not isinstance(entry, S3DirectoryMetaData):
                continue
            top = f"{entry.prefix}".removesuffix("/").split("/", 1)[0]
            if is_uuid(top):
                project_candidates.append(ProjectID(top))

        if project_candidates:
            with_fmd_rows = await _project_ids_with_fmd_rows(app, project_candidates)
            for project_id in project_candidates:
                project_id_str = f"{project_id}"
                if project_id_str in live_projects or project_id_str in with_fmd_rows:
                    continue

                if dry_run:
                    _logger.info("[DRY-RUN] Would remove orphan project prefix %s/", project_id)
                else:
                    await s3_client.delete_objects_recursively(bucket=bucket, prefix=f"{project_id}/")
                removed += 1

        if not next_cursor:
            return removed


async def _remove_unreachable_row(
    app: FastAPI,
    bucket: str,
    s3_client: SimcoreS3API,
    row: _FmdRow,
    *,
    dry_run: bool,
) -> None:
    if dry_run:
        _logger.info("[DRY-RUN] Would remove unreachable row %s", row.file_id)
        return

    if row.is_directory:
        await s3_client.delete_objects_recursively(bucket=bucket, prefix=f"{row.file_id}/")
    else:
        await s3_client.delete_object(bucket=bucket, object_key=row.file_id)
    await _delete_fmd_rows(app, [row.file_id])


# Snapshot and data access
async def _build_snapshot(app: FastAPI) -> _PassSnapshot:
    """Collect immutable reconciliation inputs for one logical pass.

    The returned snapshot is reused for every batch in the same pass so
    reachability decisions stay consistent even if projects mutate mid-pass.
    """
    started_at = datetime.now(tz=UTC)
    live_projects = await _load_live_project_ids(app)
    referenced_paths = await _load_referenced_paths(app)
    return _PassSnapshot(started_at=started_at, live_projects=live_projects, referenced_paths=referenced_paths)


async def _ensure_incremental_snapshot(app: FastAPI, redis: Any) -> _PassSnapshot:
    """Load pass snapshot from Redis or create a new one.

    A missing ``_RECONCILE_SCAN_STARTED_AT_KEY`` means no active pass exists,
    so a new snapshot is built and cursor reset to the beginning.
    """
    started_raw = await redis.get(_RECONCILE_SCAN_STARTED_AT_KEY)
    if started_raw is None:
        snapshot = await _build_snapshot(app)
        await _persist_snapshot(redis, snapshot)
        await redis.set(_RECONCILE_CURSOR_KEY, "")
        return snapshot

    started_iso = started_raw.decode() if isinstance(started_raw, bytes) else f"{started_raw}"
    started_at = datetime.fromisoformat(started_iso)

    live_projects = await _decode_redis_set(redis, _RECONCILE_LIVE_PROJECTS_KEY)
    referenced_paths = await _decode_redis_set(redis, _RECONCILE_REFERENCED_PATHS_KEY)
    return _PassSnapshot(started_at=started_at, live_projects=live_projects, referenced_paths=referenced_paths)


async def _persist_snapshot(redis: Any, snapshot: _PassSnapshot) -> None:
    """Atomically replace persisted snapshot keys.

    ``MULTI/EXEC`` ensures workers never observe mixed old/new snapshot sets.
    """
    # Persist the snapshot in one Redis transaction so other workers never
    # observe a partially replaced snapshot.
    pipe = redis.pipeline(transaction=True)
    pipe.delete(_RECONCILE_LIVE_PROJECTS_KEY, _RECONCILE_REFERENCED_PATHS_KEY)
    if snapshot.live_projects:
        pipe.sadd(_RECONCILE_LIVE_PROJECTS_KEY, *snapshot.live_projects)
    if snapshot.referenced_paths:
        pipe.sadd(_RECONCILE_REFERENCED_PATHS_KEY, *snapshot.referenced_paths)
    pipe.set(_RECONCILE_SCAN_STARTED_AT_KEY, snapshot.started_at.isoformat())
    await pipe.execute()


async def _load_live_project_ids(app: FastAPI) -> set[str]:
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(sa.select(projects.c.uuid))
        return {f"{row[0]}" for row in rows.fetchall()}


async def _load_referenced_paths(app: FastAPI) -> set[str]:
    referenced: set[str] = set()
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(sa.select(projects.c.workbench))
        for (workbench,) in rows.fetchall():
            if isinstance(workbench, dict):
                referenced.update(_extract_store_zero_paths(workbench))
    return referenced


async def _fetch_fmd_batch(app: FastAPI, cursor: str, limit: int) -> list[_FmdRow]:
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(
            sa.select(
                file_meta_data.c.file_id,
                file_meta_data.c.project_id,
                file_meta_data.c.created_at,
                file_meta_data.c.upload_expires_at,
                file_meta_data.c.is_directory,
            )
            .where(file_meta_data.c.file_id > cursor if cursor else sa.true())
            .order_by(file_meta_data.c.file_id)
            .limit(limit)
        )

        return [
            _FmdRow(
                file_id=f"{file_id}",
                project_id=f"{project_id}" if project_id else None,
                created_at=_parse_created_at(created_at_raw),
                upload_expires_at=upload_expires_at,
                is_directory=is_directory,
            )
            for file_id, project_id, created_at_raw, upload_expires_at, is_directory in rows.fetchall()
        ]


async def _project_ids_with_fmd_rows(app: FastAPI, candidate_ids: list[ProjectID]) -> set[str]:
    if not candidate_ids:
        return set()
    as_str = [f"{pid}" for pid in candidate_ids]
    async with pass_or_acquire_connection(get_db_engine(app)) as conn:
        rows = await conn.execute(
            sa.select(file_meta_data.c.project_id).where(file_meta_data.c.project_id.in_(as_str)).distinct()
        )
        return {f"{row[0]}" for row in rows.fetchall() if row[0]}


async def _delete_fmd_rows(app: FastAPI, file_ids: list[str]) -> None:
    if not file_ids:
        return
    async with get_db_engine(app).begin() as conn:
        await conn.execute(file_meta_data.delete().where(file_meta_data.c.file_id.in_(file_ids)))


# Utilities
def _log_reconcile_summary(counts: ReconciliationCounts, *, dry_run: bool, mode: str) -> None:
    prefix = "[DRY-RUN] " if dry_run else ""
    _logger.info(
        "%sv2 reconcile (%s): unreachable=%d dangling=%d orphan_prefixes=%d total=%d",
        prefix,
        mode,
        counts.unreachable_removed,
        counts.dangling_removed,
        counts.orphan_prefixes_removed,
        counts.total_removed,
    )


def _get_simcore_bucket_name(app: FastAPI) -> str:
    settings = get_application_settings(app)
    assert settings.STORAGE_S3  # nosec
    s3_settings: S3Settings = settings.STORAGE_S3
    return f"{s3_settings.S3_BUCKET_NAME}"


def _parse_created_at(created_at_raw: str | None) -> datetime:
    try:
        dt = arrow.get(created_at_raw or "").datetime
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (arrow.parser.ParserError, ValueError, TypeError):
        return datetime.min.replace(tzinfo=UTC)


def _extract_store_zero_paths(workbench: dict) -> set[str]:
    paths: set[str] = set()
    for node_data in workbench.values():
        if not isinstance(node_data, dict):
            continue
        for port_dict in (node_data.get("inputs") or {}, node_data.get("outputs") or {}):
            if not isinstance(port_dict, dict):
                continue
            for val in port_dict.values():
                if isinstance(val, dict) and val.get("store") == 0:
                    path = val.get("path")
                    if isinstance(path, str) and path:
                        paths.add(path)
    return paths


async def _decode_redis_set(redis: Any, key: str) -> set[str]:
    raw_values = await redis.smembers(key)
    return {value.decode() if isinstance(value, bytes) else f"{value}" for value in raw_values}


def _is_exports_row(file_id: str) -> bool:
    return file_id.startswith(f"{EXPORTS_S3_PREFIX}/")


def _is_reachable(row: _FmdRow, snapshot: _PassSnapshot) -> bool:
    return (row.project_id is not None and row.project_id in snapshot.live_projects) or (
        row.file_id in snapshot.referenced_paths
    )


async def _get_cursor(redis: Any) -> str:
    raw = await redis.get(_RECONCILE_CURSOR_KEY)
    if raw is None:
        return ""
    return raw.decode() if isinstance(raw, bytes) else f"{raw}"


async def _set_cursor(redis: Any, cursor: str) -> None:
    await redis.set(_RECONCILE_CURSOR_KEY, cursor)


async def _reset_pass_state(redis: Any) -> None:
    await redis.delete(
        _RECONCILE_CURSOR_KEY,
        _RECONCILE_SCAN_STARTED_AT_KEY,
        _RECONCILE_LIVE_PROJECTS_KEY,
        _RECONCILE_REFERENCED_PATHS_KEY,
    )
