import asyncio
import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Final

import aiofiles
import aiofiles.os
from annotated_types import doc
from pydantic import ByteSize, PositiveInt, TypeAdapter
from servicelib.file_utils import create_sha256_checksum

_DIGEST_CHUNK_SIZE: Final[
    Annotated[ByteSize, doc("read size per digest step; a power of two above the OS page size")]
] = TypeAdapter(ByteSize).validate_python("4MiB")


async def _hash_file(path: Path) -> str:
    async with aiofiles.open(path, mode="rb") as file:
        return await create_sha256_checksum(file, chunk_size=_DIGEST_CHUNK_SIZE)


@dataclass(frozen=True, slots=True)
class _FileEntry:
    size: int
    mtime_ns: int
    digest: str


def _directory_record(rel_path: Path) -> str:
    return f"d\x00{rel_path.as_posix()}"


def _walk_directory(directory: Path) -> tuple[list[Path], list[Path]]:
    """Returns the directory and file paths relative to ``directory``"""
    dir_rel_paths: list[Path] = []
    file_rel_paths: list[Path] = []
    for root, dir_names, file_names in os.walk(directory, followlinks=False):
        root_path = Path(root)
        dir_rel_paths.extend(root_path.joinpath(name).relative_to(directory) for name in dir_names)
        file_rel_paths.extend(root_path.joinpath(name).relative_to(directory) for name in file_names)
    return dir_rel_paths, file_rel_paths


@dataclass(frozen=True, slots=True)
class PortContentStatus:
    has_changed: bool
    is_settled: bool
    matches_last_upload: bool


@dataclass(slots=True)
class _PortState:
    fingerprint: str
    computed_at: datetime
    stable_looks: int = 0
    uploaded_fingerprint: str | None = None


class PortContentFingerprinter:
    """Tracks each port's content fingerprint over time to detect ongoing writes."""

    def __init__(self, *, required_stable_looks: PositiveInt = 5) -> None:
        self._required_stable_looks = required_stable_looks
        self._hash_cache: dict[str, dict[str, _FileEntry]] = {}
        self._ports: dict[str, _PortState] = {}

    async def observe(self, port_key: str, port_directory: Path) -> PortContentStatus:
        fingerprint = await self._scan(port_key, port_directory)
        state = self._ports.get(port_key)
        if state is None:
            self._ports[port_key] = _PortState(fingerprint=fingerprint, computed_at=datetime.now(tz=UTC))
            return PortContentStatus(has_changed=True, is_settled=False, matches_last_upload=False)
        if state.fingerprint != fingerprint:
            state.fingerprint = fingerprint
            state.computed_at = datetime.now(tz=UTC)
            state.stable_looks = 0
            return PortContentStatus(
                has_changed=True,
                is_settled=False,
                matches_last_upload=fingerprint == state.uploaded_fingerprint,
            )
        state.stable_looks += 1
        return PortContentStatus(
            has_changed=False,
            is_settled=state.stable_looks >= self._required_stable_looks,
            matches_last_upload=fingerprint == state.uploaded_fingerprint,
        )

    async def note_upload_succeeded(self, port_key: str, port_directory: Path) -> bool:
        """Records the current fingerprint as uploaded, returns True if content did not change during the upload."""
        fingerprint = await self._scan(port_key, port_directory)
        state = self._ports.get(port_key)
        if state is None:
            self._ports[port_key] = _PortState(
                fingerprint=fingerprint,
                computed_at=datetime.now(tz=UTC),
                uploaded_fingerprint=fingerprint,
            )
            return True
        if state.fingerprint != fingerprint:
            state.fingerprint = fingerprint
            state.computed_at = datetime.now(tz=UTC)
            state.stable_looks = 0
            return False
        state.uploaded_fingerprint = fingerprint
        return True

    async def _scan(self, port_key: str, directory: Path) -> str:
        records: list[str] = []
        port_hash_cache = self._hash_cache.setdefault(port_key, {})
        if await aiofiles.os.path.isdir(directory):
            dir_rel_paths, file_rel_paths = await asyncio.to_thread(_walk_directory, directory)
            records.extend(_directory_record(rel_path) for rel_path in dir_rel_paths)

            seen_rel_paths: set[str] = set()
            records.extend(
                [
                    await _record_for_file(directory / rel_path, rel_path, port_hash_cache, seen_rel_paths)
                    for rel_path in file_rel_paths
                ]
            )
            # cache entries of files gone since this scan can never be hit again
            self._hash_cache[port_key] = {k: v for k, v in port_hash_cache.items() if k in seen_rel_paths}

        hasher = hashlib.sha256()
        for record in sorted(records):
            hasher.update(record.encode())
            hasher.update(b"\n")
        return hasher.hexdigest()


async def _record_for_file(
    path: Path,
    rel_path: Path,
    port_hash_cache: dict[str, _FileEntry],
    seen_rel_paths: set[str],
) -> str:
    rel_path_posix = rel_path.as_posix()
    # marking before the stat keeps the cache entry alive for vanishing files
    seen_rel_paths.add(rel_path_posix)
    try:
        stat_result = await aiofiles.os.stat(path)
    except OSError:
        link_target = await aiofiles.os.readlink(f"{path}")
        return f"x\x00{rel_path_posix}\x00{link_target}"
    cached = port_hash_cache.get(rel_path_posix)
    if cached is not None and cached.size == stat_result.st_size and cached.mtime_ns == stat_result.st_mtime_ns:
        digest = cached.digest
    else:
        digest = await _hash_file(path)
        port_hash_cache[rel_path_posix] = _FileEntry(
            size=stat_result.st_size,
            mtime_ns=stat_result.st_mtime_ns,
            digest=digest,
        )
    return f"f\x00{rel_path_posix}\x00{stat_result.st_size}\x00{digest}"
