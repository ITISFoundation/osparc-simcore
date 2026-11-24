"""Quiet-trigger content tracking for the outputs upload policy."""

import asyncio
import logging
import os
import stat as stat_module
from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Annotated, Final
from uuid import uuid4

import xxhash
from annotated_types import doc
from pydantic import ByteSize, PositiveFloat, PositiveInt, TypeAdapter

_logger = logging.getLogger(__name__)

_QUIET_SECONDS: Final[Annotated[PositiveFloat, doc("time without events after which the content is checked")]] = 3.0

_EPISODE_MAX_SCANS: Final[Annotated[PositiveInt, doc("scans an episode may use to prove the content stable")]] = 3

_HASH_CHUNK_SIZE: Final[
    Annotated[ByteSize, doc("read size per hashing step; a power of two above the OS page size")]
] = TypeAdapter(ByteSize).validate_python("4MiB")

DEFAULT_HASH_WORKERS: Final[Annotated[int, doc("files hashed concurrently by the shared pool")]] = 4

type OnStableChangeCB = Callable[[str], Awaitable[None]]


class CheckOutcome(Enum):
    STABLE_MATCHING = auto()  # equal to the last uploaded fingerprint
    STABLE_NEW = auto()  # different from the last uploaded fingerprint
    UNSTABLE = auto()  # the episode ended with the content still moving


@dataclass(slots=True)
class _ScanResult:
    fingerprint: str
    pending_hashes: int


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
        while chunk := file.read(_HASH_CHUNK_SIZE):
            hasher.update(chunk)
        stat_after = os.fstat(file.fileno())
    return hasher.digest(), stat_after


def _fill_digest(job: tuple[str, _FileRecord]) -> None:
    path_str, record = job
    try:
        digest, stat_after = _hash_file(Path(path_str))
    except OSError as err:
        # a changing digest keeps the port unstable, so saves still upload it
        _logger.warning("port file %s cannot be hashed (%s), treating it as changed", path_str, err)
        record.digest = uuid4().bytes
        return
    record.digest = digest
    record.digest_size = stat_after.st_size
    record.digest_mtime_ns = stat_after.st_mtime_ns


def _broken_link_kind(entry: os.DirEntry[str]) -> str:
    """Returns the kind string of an entry that cannot be stat'ed."""
    with suppress(OSError):
        # readlink can fail as well: ENAMETOOLONG on a deep tree
        return f"x{Path(entry.path).readlink()}"
    return f"n{entry.name}"


def _nonfile_record(kind: str) -> _FileRecord:
    """Ledger entry for a non-regular file: identified by kind, never hashed, always stable."""
    return _FileRecord(
        digest=os.fsencode(f"s{kind}"),
        digest_size=None,
        digest_mtime_ns=None,
        seen_size=-1,
        seen_mtime_ns=-1,
    )


def _unlistable_record() -> _FileRecord:
    """Ledger entry for a directory that cannot be listed: pending forever, so nothing certifies it."""
    return _FileRecord(
        digest=None,
        digest_size=None,
        digest_mtime_ns=None,
        seen_size=-1,
        seen_mtime_ns=-1,
    )


def _compute_fingerprint(entries: dict[str, _FileRecord]) -> str:
    hasher = xxhash.xxh3_64()
    for rel_path in sorted(entries):
        record = entries[rel_path]
        if record.digest is None:
            entry_text = f"p\x00{rel_path}"  # a pending hash never equals a settled record
        elif record.seen_size < 0:  # a non-file record carries its kind in digest
            entry_text = f"{os.fsdecode(record.digest)}\x00{rel_path}"
        else:
            entry_text = f"f\x00{rel_path}\x00{record.digest_size}\x00{record.digest.hex()}"
        hasher.update(os.fsencode(entry_text))
        hasher.update(b"\n")
    return hasher.hexdigest()


class PortFingerprint:  # pylint: disable=too-many-instance-attributes
    """Tracks one port directory: events arm a timer; quiet expiry runs the scan checks."""

    def __init__(
        self,
        *,
        port_key: str,
        directory: Path,
        hash_executor: ThreadPoolExecutor,
        on_stable_change: OnStableChangeCB,
    ) -> None:
        self._port_key = port_key
        self._directory = directory
        self._hash_executor = hash_executor
        self._on_stable_change = on_stable_change

        self._entries: dict[str, _FileRecord] = {}
        self._fingerprint: str | None = None
        self._uploaded_fingerprint: str | None = None
        self._upload_candidate: str | None = None
        self._pending_hashes: int = 0

        self._scan_lock = asyncio.Lock()
        self._episode_seq = 0
        self._episode_task: asyncio.Task[None] | None = None

    def note_event(self) -> None:
        """Records filesystem activity: the check episode starts `_QUIET_SECONDS` after the last one."""
        self._episode_seq += 1  # invalidates any episode already running
        if self._episode_task is not None and not self._episode_task.done():
            self._episode_task.cancel()
        self._episode_task = asyncio.create_task(
            self._armed_episode(self._episode_seq), name=f"fingerprint_quiet_{self._port_key}"
        )

    def has_pending_work(self) -> bool:
        """True while an armed timer or a running check could still schedule an upload."""
        return self._episode_task is not None and not self._episode_task.done()

    async def _armed_episode(self, seq: int) -> None:
        with suppress(asyncio.CancelledError):
            await asyncio.sleep(_QUIET_SECONDS)
        if seq != self._episode_seq:
            return  # a newer event took over
        outcome = await self._run_episode(seq)
        if outcome is CheckOutcome.STABLE_NEW and seq == self._episode_seq:
            await self._on_stable_change(self._port_key)

    async def check_now(self) -> CheckOutcome:
        """Runs a check episode immediately (save path); cancels any armed episode."""
        self._episode_seq += 1
        if self._episode_task is not None and not self._episode_task.done():
            self._episode_task.cancel()
            with suppress(CancelledError):
                await self._episode_task
        seq = self._episode_seq
        outcome = await self._run_episode(seq)
        return outcome if outcome is not None else CheckOutcome.UNSTABLE

    async def sweep(self) -> None:
        """Background safety check for lost events; skips ports whose own timer owns the decision."""
        if self.has_pending_work():
            return
        outcome = await self._run_episode(self._episode_seq)
        if outcome is CheckOutcome.STABLE_NEW:
            _logger.info("port %s: safety sweep found unuploaded content", self._port_key)
            await self._on_stable_change(self._port_key)

    def shutdown(self) -> None:
        self._episode_seq += 1  # a running episode sees a stale sequence and stops
        if self._episode_task is not None and not self._episode_task.done():
            self._episode_task.cancel()

    async def _run_episode(self, seq: int) -> CheckOutcome | None:
        """Scans until two finished scans agree; None when an event abandoned the episode."""
        previous: _ScanResult | None = None
        outcome: CheckOutcome | None = None
        try:
            for _ in range(_EPISODE_MAX_SCANS):
                if seq != self._episode_seq:
                    break
                try:
                    result = await self._scan()
                except asyncio.CancelledError:
                    break
                if seq != self._episode_seq:
                    break
                if result.pending_hashes > 0:
                    previous = None  # a half-scanned port cannot confirm anything
                    continue
                if previous is not None and result.fingerprint == previous.fingerprint:
                    outcome = (
                        CheckOutcome.STABLE_MATCHING
                        if result.fingerprint == self._uploaded_fingerprint
                        else CheckOutcome.STABLE_NEW
                    )
                    break
                previous = result
            else:
                outcome = CheckOutcome.UNSTABLE
        except Exception:  # pylint: disable=broad-except
            _logger.warning("port %s content check failed, will retry", self._port_key, exc_info=True)
            return None
        return outcome

    async def _scan(self) -> _ScanResult:
        async with self._scan_lock:
            loop = asyncio.get_running_loop()
            entries, hash_jobs = await asyncio.to_thread(self._collect_entries)
            if hash_jobs:
                # hashing runs after the stat pass and covers only the files that changed
                await asyncio.gather(
                    *(loop.run_in_executor(self._hash_executor, _fill_digest, job) for job in hash_jobs)
                )
            fingerprint = await asyncio.to_thread(_compute_fingerprint, entries)

            self._entries = entries
            self._fingerprint = fingerprint
            self._pending_hashes = sum(1 for record in entries.values() if record.digest is None)
            return _ScanResult(fingerprint=fingerprint, pending_hashes=self._pending_hashes)

    def take_upload_candidate(self) -> str | None:
        """Captures the confirmed fingerprint an upload would send; None while content is in motion."""
        if self._pending_hashes > 0 or self._fingerprint is None:
            return None
        return self._fingerprint

    def note_upload_started(self, fingerprint: str) -> None:
        """Records the captured fingerprint the upload is sending, verified after the PUT."""
        self._upload_candidate = fingerprint

    def note_upload_uncertified(self) -> None:
        """Clears the certification of an unidentified PUT: its content stays eligible."""
        self._upload_candidate = None
        self._uploaded_fingerprint = None

    async def verify_upload_completed(self) -> bool:
        """Rescans after a successful PUT; records the content as uploaded unless it changed."""
        if self._episode_task is not None and not self._episode_task.done():
            self._episode_task.cancel()
            with suppress(CancelledError):
                await self._episode_task
        await self._scan()
        unchanged = (
            self._pending_hashes == 0 and self._fingerprint is not None and self._fingerprint == self._upload_candidate
        )
        if unchanged:
            self._uploaded_fingerprint = self._fingerprint
        return unchanged

    def _collect_entries(self) -> tuple[dict[str, _FileRecord], list[tuple[str, _FileRecord]]]:
        """Lists and stats the tree, then queues only the files that changed for hashing."""
        entries: dict[str, _FileRecord] = {}
        hash_jobs: list[tuple[str, _FileRecord]] = []
        pending_directories: list[tuple[str, str]] = [(str(self._directory), "")]
        while pending_directories:
            directory, prefix = pending_directories.pop()
            self._list_directory(directory, prefix, entries, hash_jobs, pending_directories)
        return entries, hash_jobs

    def _list_directory(
        self,
        directory: str,
        prefix: str,
        entries: dict[str, _FileRecord],
        hash_jobs: list[tuple[str, _FileRecord]],
        pending_directories: list[tuple[str, str]],
    ) -> None:
        """Lists one directory; subdirectories join `pending_directories` for a later round"""
        try:
            scandir_iterator = os.scandir(directory)
        except FileNotFoundError:
            if prefix:
                return  # the directory vanished mid-scan: the next scan sees what is there now
            # a missing port root hides all content: an empty listing here must never certify or upload
            _logger.warning("port directory %s is missing, content unverified", directory)
            entries[f"{prefix}."] = _unlistable_record()
            return
        except OSError as err:
            # an unlistable directory hides content: the port stays pending until it can be read again
            _logger.warning("port directory %s cannot be listed (%s), content unverified", directory, err)
            entries[f"{prefix}."] = _unlistable_record()
            return
        with scandir_iterator:
            for entry in scandir_iterator:
                rel_path = f"{prefix}{entry.name}"
                try:
                    stat_result = entry.stat(follow_symlinks=True)
                except OSError:
                    entries[rel_path] = _nonfile_record(_broken_link_kind(entry))
                    continue
                if entry.is_dir(follow_symlinks=False):
                    entries[rel_path] = _nonfile_record("d")
                    pending_directories.append((entry.path, f"{rel_path}/"))
                    continue
                if not stat_module.S_ISREG(stat_result.st_mode):
                    entries[rel_path] = _nonfile_record(f"x{entry.path}")
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
        # mid-write content is incomplete: hashing waits for a size and mtime repeat
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
