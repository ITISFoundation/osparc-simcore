"""Per-port content tracking for the outputs upload policy.

One `PortFingerprint` object per output port owns the whole lifecycle of that port:
its file ledger, its fingerprint, its settle counter, and the fingerprint of its last
successful upload. Objects never share state, so activity on one port can never make
another port look changed.
"""

import asyncio
import logging
import os
import stat as stat_module
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Final

import xxhash
from annotated_types import doc
from pydantic import ByteSize, PositiveFloat, PositiveInt, TypeAdapter

_logger = logging.getLogger(__name__)

_HASH_CHUNK_SIZE: Final[
    Annotated[ByteSize, doc("read size per hashing step; a power of two above the OS page size")]
] = TypeAdapter(ByteSize).validate_python("4MiB")

DEFAULT_HASH_WORKERS: Final[Annotated[int, doc("files hashed concurrently by the shared pool")]] = 4

_DEFAULT_REQUIRED_STABLE_LOOKS: Final[
    Annotated[PositiveInt, doc("scans with an unchanged fingerprint required before an upload is allowed")]
] = 5

_DEFAULT_MIN_SCAN_INTERVAL: Final[Annotated[PositiveFloat, doc("minimum time between two scans of the same port")]] = (
    timedelta(seconds=1).total_seconds()
)


@dataclass(slots=True)
class _FileRecord:
    digest: Annotated[bytes | None, doc("None until the file is quiet and hashed")]
    digest_size: Annotated[int | None, doc("size the digest was computed from")]
    digest_mtime_ns: Annotated[int | None, doc("mtime the digest was computed from")]
    seen_size: Annotated[int, doc("size observed by the most recent scan")]
    seen_mtime_ns: Annotated[int, doc("mtime observed by the most recent scan")]


def _hash_file(path: Path) -> tuple[bytes, os.stat_result]:
    hasher = xxhash.xxh3_64()
    with path.open("rb") as file:
        while chunk := file.read(int(_HASH_CHUNK_SIZE)):
            hasher.update(chunk)
        stat_after = os.fstat(file.fileno())
    return hasher.digest(), stat_after


def _fill_digest(job: tuple[str, _FileRecord]) -> None:
    path_str, record = job
    try:
        digest, stat_after = _hash_file(Path(path_str))
    except OSError:
        return  # the digest stays missing; the next scan sees the file gone or changed
    record.digest = digest
    record.digest_size = stat_after.st_size
    record.digest_mtime_ns = stat_after.st_mtime_ns


class PortFingerprint:  # pylint: disable=too-many-instance-attributes
    """Tracks one port directory: cheap scans flag changes, hashes confirm content."""

    def __init__(
        self,
        *,
        directory: Path,
        hash_executor: ThreadPoolExecutor,
    ) -> None:
        self._directory = directory
        self._hash_executor = hash_executor

        self._entries: dict[str, _FileRecord] = {}
        self._fingerprint: str | None = None
        self._uploaded_fingerprint: str | None = None
        self._upload_candidate: str | None = None
        self._stable_looks: int = 0
        self._pending_hashes: int = 0
        self._dirty: bool = True
        self._changed_mid_scan: bool = False
        self._last_scan_mono: float = 0.0
        self._scan_task: asyncio.Task[None] | None = None

    # -- scan scheduling -------------------------------------------------------

    def mark_dirty(self) -> None:
        """Records filesystem activity for this port; the scan itself runs on a later tick."""
        self._dirty = True

    def request_scan(self, *, force: bool = False) -> None:
        """Starts a background scan when one is due; at most one scan runs per port at a time."""
        if self._is_scanning():
            return
        if not (self._dirty or force):
            return
        if time.monotonic() - self._last_scan_mono < _DEFAULT_MIN_SCAN_INTERVAL:
            return
        self._scan_task = asyncio.create_task(self._guarded_scan(), name=f"fingerprint_scan_{self._directory.name}")

    def _is_scanning(self) -> bool:
        return self._scan_task is not None and not self._scan_task.done()

    def has_unscanned_demand(self) -> bool:
        """True while an event or a tick asked for a scan that has not completed yet."""
        return self._dirty or self._is_scanning()

    async def _scan_now(self) -> None:
        """Runs a scan inline, bypassing the interval cap; waits out a scan already running."""
        if self._scan_task is not None:
            with suppress(asyncio.CancelledError):
                await self._scan_task
        await self._scan()

    def shutdown(self) -> None:
        if self._scan_task is not None and not self._scan_task.done():
            self._scan_task.cancel()

    # -- upload decision interface ---------------------------------------------

    def is_settled(self) -> bool:
        """True when the confirmed fingerprint stopped changing for the required number of scans.

        The in-scan change flag is deliberately not consulted: it is the early signal only,
        and a persistent change always shifts the fingerprint or leaves a pending hash.
        """
        if self._pending_hashes > 0:
            return False
        if self._fingerprint is None:
            return False
        return self._stable_looks >= _DEFAULT_REQUIRED_STABLE_LOOKS

    def matches_last_upload(self) -> bool:
        """True when the settled fingerprint is the one recorded by the last successful upload."""
        return self.is_settled() and self._fingerprint == self._uploaded_fingerprint

    def take_upload_candidate(self) -> str | None:
        """Atomically captures the settled fingerprint an upload would send; None while unsettled."""
        return self._fingerprint if self.is_settled() else None

    def note_upload_started(self, fingerprint: str) -> None:
        """Records the captured fingerprint the upload is sending, verified after the PUT."""
        self._upload_candidate = fingerprint

    async def verify_upload_completed(self) -> bool:
        """Rescans after a successful PUT; records the content as uploaded unless it changed."""
        await self._scan_now()
        unchanged = (
            self._pending_hashes == 0 and self._fingerprint is not None and self._fingerprint == self._upload_candidate
        )
        if unchanged:
            self._uploaded_fingerprint = self._fingerprint
        return unchanged

    # -- the scan ---------------------------------------------------------------

    async def _guarded_scan(self) -> None:
        try:
            await self._scan()
        except Exception:  # pylint: disable=broad-except
            self._dirty = True  # retry on the next tick with the demand kept alive
            _logger.warning("port %s fingerprint scan failed, will retry", self._directory.name, exc_info=True)

    async def _scan(self) -> None:
        self._dirty = False
        self._changed_mid_scan = False
        self._last_scan_mono = time.monotonic()
        scan_started = time.perf_counter()
        loop = asyncio.get_running_loop()

        entries, hash_jobs = await asyncio.to_thread(self._collect_entries)
        if hash_jobs:
            # the heavier step runs last: digests of quiet-changed files, pool-sized at a time
            await asyncio.gather(*(loop.run_in_executor(self._hash_executor, _fill_digest, job) for job in hash_jobs))
        fingerprint = await asyncio.to_thread(_compute_fingerprint, entries)

        self._pending_hashes = sum(1 for record in entries.values() if record.digest is None)
        if self._pending_hashes == 0 and fingerprint == self._fingerprint:
            self._stable_looks = min(self._stable_looks + 1, _DEFAULT_REQUIRED_STABLE_LOOKS)
        else:
            self._fingerprint = fingerprint
            self._stable_looks = 0
        self._entries = entries
        _logger.debug(
            "port %s scan took %.3fs: %s entries, %s hashed, %s awaiting hashes, changed=%s",
            self._directory.name,
            time.perf_counter() - scan_started,
            len(entries),
            len(hash_jobs),
            self._pending_hashes,
            self._changed_mid_scan,
        )

    def _collect_entries(self) -> tuple[dict[str, _FileRecord], list[tuple[str, _FileRecord]]]:
        """Walk + stat pass: the cheap checks run first so a change is flagged before any hashing."""
        entries: dict[str, _FileRecord] = {}
        hash_jobs: list[tuple[str, _FileRecord]] = []
        self._walk(self._directory, "", entries, hash_jobs)
        return entries, hash_jobs

    def _walk(
        self,
        directory: Path,
        prefix: str,
        entries: dict[str, _FileRecord],
        hash_jobs: list[tuple[str, _FileRecord]],
    ) -> None:
        try:
            scandir_iterator = os.scandir(directory)
        except OSError:
            # the directory vanished mid-scan: the next scan sees what is there now
            self._changed_mid_scan = True
            return
        with scandir_iterator:
            for entry in scandir_iterator:
                rel_path = f"{prefix}{entry.name}"
                try:
                    stat_result = entry.stat(follow_symlinks=True)
                except OSError:
                    entries[rel_path] = _special_record(_broken_link_kind(entry))
                    continue
                if entry.is_dir(follow_symlinks=False):
                    entries[rel_path] = _special_record("d")
                    self._walk(Path(entry.path), f"{rel_path}/", entries, hash_jobs)
                    continue
                if not stat_module.S_ISREG(stat_result.st_mode):
                    entries[rel_path] = _special_record(f"x{entry.path}")
                    continue
                self._track_file(rel_path, Path(entry.path), stat_result, entries, hash_jobs)

    def _track_file(
        self,
        rel_path: str,
        path: Path,
        stat_result: os.stat_result,
        entries: dict[str, _FileRecord],
        hash_jobs: list[tuple[str, _FileRecord]],
    ) -> None:
        old = self._entries.get(rel_path)
        if (
            old is not None
            and old.digest is not None
            and old.digest_size == stat_result.st_size
            and old.digest_mtime_ns == stat_result.st_mtime_ns
        ):
            entries[rel_path] = old  # size and mtime unchanged: the stored digest stands
            return
        self._changed_mid_scan = True
        # a file hashes only once its stat repeated from one scan to the next: mid-write
        # content is incomplete, and re-reading it every scan would be pure waste
        quiet_since_last_scan = (
            old is not None and old.seen_size == stat_result.st_size and old.seen_mtime_ns == stat_result.st_mtime_ns
        )
        record = _FileRecord(
            digest=None,
            digest_size=None,
            digest_mtime_ns=None,
            seen_size=stat_result.st_size,
            seen_mtime_ns=stat_result.st_mtime_ns,
        )
        entries[rel_path] = record
        if quiet_since_last_scan:
            hash_jobs.append((str(path), record))


def _broken_link_kind(entry: os.DirEntry[str]) -> str:
    """Identifies an unstatable entry; the readlink can fail too (e.g. ENAMETOOLONG deep links)."""
    with suppress(OSError):
        return f"x{Path(entry.path).readlink()}"
    return f"n{entry.name}"


def _special_record(kind: str) -> _FileRecord:
    return _FileRecord(
        digest=f"s{kind}".encode(),
        digest_size=0,
        digest_mtime_ns=0,
        seen_size=-1,
        seen_mtime_ns=-1,
    )


def _compute_fingerprint(entries: dict[str, _FileRecord]) -> str:
    hasher = xxhash.xxh3_64()
    for rel_path in sorted(entries):
        record = entries[rel_path]
        if record.digest is None:
            entry_text = f"p\x00{rel_path}"  # pending hash: never equals a settled entry record
        elif record.digest_size == 0:  # directory or special entry, digest carries the kind
            entry_text = f"{record.digest.decode(errors='replace')}\x00{rel_path}"
        else:
            entry_text = f"f\x00{rel_path}\x00{record.digest_size}\x00{record.digest.hex()}"
        hasher.update(entry_text.encode(errors="replace"))
        hasher.update(b"\n")
    return hasher.hexdigest()
