"""Stability tracking of one output port directory: filesystem knowledge only, no upload state."""

import asyncio
import logging
import os
import stat as stat_module
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Annotated, Final, NamedTuple
from uuid import uuid4

import xxhash
from annotated_types import doc
from pydantic import ByteSize, PositiveFloat, PositiveInt, TypeAdapter

_logger = logging.getLogger(__name__)

_QUIET_SECONDS: Final[Annotated[PositiveFloat, doc("time without events after which the content is checked")]] = 3.0

_STABILITY_MAX_SCANS: Final[
    Annotated[PositiveInt, doc("scans one stability check may use to prove the content stable")]
] = 3

_HASH_CHUNK_SIZE: Final[
    Annotated[ByteSize, doc("read size per hashing step; a power of two above the OS page size")]
] = TypeAdapter(ByteSize).validate_python("4MiB")

_NO_METADATA_SENTINEL: Final[Annotated[int, doc("size and mtime value for records that describe no regular file")]] = -1

DEFAULT_HASH_WORKERS: Final[Annotated[int, doc("files hashed concurrently by the shared pool")]] = 4

type OnStableContentCB = Annotated[
    Callable[[str, str], Awaitable[None]], doc("called with (port_key, fingerprint) once content settles")
]


class StabilityOutcome(Enum):
    STABLE = auto()  # two finished scans agreed and no hash is pending
    UNSTABLE = auto()  # the content was still changing when the check ended


class ContentCheckResult(NamedTuple):
    outcome: StabilityOutcome
    fingerprint: Annotated[str | None, doc("the proven fingerprint when STABLE, None otherwise")]


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


class _HashedFile(NamedTuple):
    digest: bytes
    stat_result: os.stat_result


def _hash_file(path: Path) -> _HashedFile:
    hasher = xxhash.xxh3_64()
    with path.open("rb") as file:
        while chunk := file.read(_HASH_CHUNK_SIZE):
            hasher.update(chunk)
        # fstat on the descriptor pairs the stat with the hashed bytes even if the path is renamed mid-read
        stat_after = os.fstat(file.fileno())
    return _HashedFile(digest=hasher.digest(), stat_result=stat_after)


def _fill_digest(job: tuple[str, _FileRecord]) -> None:
    path_str, record = job
    try:
        hashed = _hash_file(Path(path_str))
    except FileNotFoundError:
        # files vanishing while the container writes is expected churn
        _logger.debug("port file %s vanished while hashing, treating it as changed", path_str)
        record.digest = uuid4().bytes
        return
    except OSError as err:
        # a changing digest keeps the port unstable, so saves still upload it
        _logger.warning("port file %s cannot be hashed (%s), treating it as changed", path_str, err)
        record.digest = uuid4().bytes
        return
    record.digest = hashed.digest
    record.digest_size = hashed.stat_result.st_size
    record.digest_mtime_ns = hashed.stat_result.st_mtime_ns


def _broken_link_kind(entry: os.DirEntry[str]) -> str:
    """Kind string identifying an entry that cannot be stat'ed: its link target when readable,
    otherwise its name"""
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
        seen_size=_NO_METADATA_SENTINEL,
        seen_mtime_ns=_NO_METADATA_SENTINEL,
    )


def _unlistable_record() -> _FileRecord:
    """Ledger entry for a directory that cannot be listed: pending forever, so nothing certifies it."""
    return _FileRecord(
        digest=None,
        digest_size=None,
        digest_mtime_ns=None,
        seen_size=_NO_METADATA_SENTINEL,
        seen_mtime_ns=_NO_METADATA_SENTINEL,
    )


def _compute_fingerprint(entries: dict[str, _FileRecord]) -> str:
    hasher = xxhash.xxh3_64()
    for rel_path in sorted(entries):
        record = entries[rel_path]
        if record.digest is None:
            entry_text = f"p\x00{rel_path}"  # a pending hash never equals a settled record
        elif record.seen_size == _NO_METADATA_SENTINEL:  # a non-file record carries its kind in digest
            entry_text = f"{os.fsdecode(record.digest)}\x00{rel_path}"
        else:
            entry_text = f"f\x00{rel_path}\x00{record.digest_size}\x00{record.digest.hex()}"
        hasher.update(os.fsencode(entry_text))
        hasher.update(b"\n")
    return hasher.hexdigest()


async def _await_cancelled_task(task: asyncio.Task[None]) -> None:
    """Awaits a task the caller has just cancelled: consumes the task's own cancellation and
    propagates a cancellation aimed at the awaiting code instead"""
    await asyncio.wait((task,))  # the task's exception/cancellation does not cross this await
    if not task.cancelled():
        task.result()  # re-raises the task's own failure, as awaiting it directly did


class PortContentMonitor:  # pylint: disable=too-many-instance-attributes
    """Tracks one port directory: filesystem events arm a timer; quiet expiry runs a stability check.
    Reports settled content through `on_stable_content`; knows nothing about uploads."""

    def __init__(
        self,
        *,
        port_key: str,
        directory: Path,
        hash_executor: ThreadPoolExecutor,
        on_stable_content: OnStableContentCB,
    ) -> None:
        self._port_key = port_key
        self._directory = directory
        self._hash_executor = hash_executor
        self._on_stable_content = on_stable_content

        self._entries: dict[str, _FileRecord] = {}
        self._fingerprint: str | None = None
        self._pending_hashes: int = 0

        self._scan_lock = asyncio.Lock()
        self._check_generation = 0
        self._check_task: asyncio.Task[None] | None = None

    def record_filesystem_event(self) -> None:
        """Records filesystem activity: the stability check runs `_QUIET_SECONDS` after the last event."""
        self._check_generation += 1  # invalidates any check already running
        self._cancel_armed_check()
        self._check_task = asyncio.create_task(
            self._arm_stability_check(self._check_generation), name=f"content_stability_check_{self._port_key}"
        )

    def has_pending_work(self) -> bool:
        """True while an armed timer or a running check could still report stable content."""
        return self._check_task is not None and not self._check_task.done()

    async def check_now(self) -> ContentCheckResult:
        """Runs a stability check immediately (save path); cancels any armed check."""
        self._check_generation += 1
        if self._check_task is not None and not self._check_task.done():
            self._check_task.cancel()
            await _await_cancelled_task(self._check_task)
        return await self._run_stability_check(self._check_generation)

    async def sweep(self) -> None:
        """Background safety check for lost events; skips ports whose own timer owns the decision."""
        if self.has_pending_work():
            return
        result = await self._run_stability_check(self._check_generation)
        if result.outcome is StabilityOutcome.STABLE and (fingerprint := result.fingerprint) is not None:
            await self._on_stable_content(self._port_key, fingerprint)

    def stable_fingerprint(self) -> str | None:
        """The current fingerprint while the last scan left no hash pending; None while content is
        in motion. Reads the last scan only, it does not run one."""
        if self._pending_hashes > 0 or self._fingerprint is None:
            return None
        return self._fingerprint

    async def rescan(self) -> str | None:
        """Cancels any armed check and scans once; the fingerprint when the scan leaves no hash pending"""
        self._check_generation += 1
        if self._check_task is not None and not self._check_task.done():
            self._check_task.cancel()
            await _await_cancelled_task(self._check_task)
        await self._scan()
        return self.stable_fingerprint()

    def shutdown(self) -> None:
        self._check_generation += 1  # a running check sees a stale generation and stops
        self._cancel_armed_check()

    def _cancel_armed_check(self) -> None:
        if self._check_task is not None and not self._check_task.done():
            self._check_task.cancel()

    async def _arm_stability_check(self, generation: int) -> None:
        # cancellation ends the check: no scan and no report run after a cancel
        await asyncio.sleep(_QUIET_SECONDS)
        if generation != self._check_generation:
            return  # a newer event took over
        result = await self._run_stability_check(generation)
        if (
            result.outcome is StabilityOutcome.STABLE
            and (fingerprint := result.fingerprint) is not None
            and generation == self._check_generation
        ):
            await self._on_stable_content(self._port_key, fingerprint)

    async def _run_stability_check(self, generation: int) -> ContentCheckResult:
        """Scans until two finished scans agree; UNSTABLE when they do not, an event takes over,
        or a scan fails"""
        try:
            return await self._scan_until_agreement(generation)
        except Exception:  # pylint: disable=broad-except
            _logger.warning("port %s content check failed, will retry", self._port_key, exc_info=True)
            return ContentCheckResult(outcome=StabilityOutcome.UNSTABLE, fingerprint=None)

    async def _scan_until_agreement(self, generation: int) -> ContentCheckResult:
        previous: _ScanResult | None = None
        for _ in range(_STABILITY_MAX_SCANS):
            if generation != self._check_generation:
                break
            result = await self._scan()  # cancellation propagates: the check stops here
            if generation != self._check_generation:
                break
            if result.pending_hashes > 0:
                previous = None  # a half-scanned port cannot confirm anything
                continue
            if previous is not None and result.fingerprint == previous.fingerprint:
                return ContentCheckResult(outcome=StabilityOutcome.STABLE, fingerprint=result.fingerprint)
            previous = result
        return ContentCheckResult(outcome=StabilityOutcome.UNSTABLE, fingerprint=None)

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
