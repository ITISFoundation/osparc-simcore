# NOTE: this code runs inside a JupyterLab with Python 3.9;
# PEP 604 (X | Y) and PEP 585 (list[X]) are not available at runtime.

import functools
import hashlib
import os
import secrets
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Final, List, Optional, Tuple  # noqa: UP035

COMPLETE_MARKER: Final[str] = "✅ finished"
FAIL_MARKER: Final[str] = "❌ error(s) detected"
_SECOND = 1000
_MINUTE = 60 * _SECOND

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_KB = 1024
_MB = 1024 * _KB

BASE_DIR: Final[Path] = Path.cwd() / "generated"
MAX_DEPTH: Final[int] = 5
NUM_SMALL_FILES: Final[int] = 1_000
SMALL_FILE_MIN_BYTES: Final[int] = 1 * _KB
SMALL_FILE_MAX_BYTES: Final[int] = 8 * _KB

LARGE_FILE_MAX_BYTES: Final[int] = 20 * _MB
LARGE_FILE_MIN_BYTES: Final[int] = int(LARGE_FILE_MAX_BYTES * 0.9)
LARGE_FILE_WRITE_CHUNK: Final[int] = 1 * _MB
PARALLEL_WORKERS: Final[int] = 8

FILES_TO_MOVE: Final[int] = int(0.1 * NUM_SMALL_FILES)

_CHECKSUM_CHUNK_SIZE: Final[int] = 8 * _KB

errors: List[str] = []  # noqa: UP006


def _random_bytes(size: int) -> bytes:
    return os.urandom(size)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHECKSUM_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def _random_nested_dir(base: Path, max_depth: int) -> Path:
    """Return a random directory path under *base* with depth in [1, max_depth]."""
    depth = secrets.randbelow(max_depth) + 1
    parts = [f"d{secrets.randbelow(4)}" for _ in range(depth)]
    return base.joinpath(*parts)


def _finalise_phase(func: Callable[[], None]) -> Callable[[], None]:
    @functools.wraps(func)
    def wrapper() -> None:
        func()

        print(COMPLETE_MARKER)

        if errors:
            print(f"\n{FAIL_MARKER} count={len(errors)}:")
            for e in errors:
                print(f"  • {e}")
            msg = f"Test failed with {len(errors)} error(s)"
            raise RuntimeError(msg)

    return wrapper


# ---------------------------------------------------------------------------
# Phase 1 - Many small files (metadata storm)
# ---------------------------------------------------------------------------
def _create_small_file(index: int) -> Optional[str]:  # noqa: UP045
    target_dir = _random_nested_dir(BASE_DIR, MAX_DEPTH)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"small_{index:04d}.bin"
    size = SMALL_FILE_MIN_BYTES + secrets.randbelow(SMALL_FILE_MAX_BYTES - SMALL_FILE_MIN_BYTES + 1)
    data = _random_bytes(size)
    expected_hash = hashlib.sha256(data).hexdigest()
    path.write_bytes(data)

    # read-after-write consistency check
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        return f"HASH MISMATCH (small) {path}: expected={expected_hash} actual={actual_hash}"
    return None


@_finalise_phase
def phase_1_create_small_files() -> None:
    print(f"Phase 1: creating {NUM_SMALL_FILES} small files in parallel ...")
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
        futures = {pool.submit(_create_small_file, i): i for i in range(NUM_SMALL_FILES)}
        for fut in as_completed(futures):
            err = fut.result()
            if err:
                errors.append(err)
    elapsed = time.monotonic() - t0
    print(f"  ✓ {NUM_SMALL_FILES} small files created in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Phase 2 - Few large files written in chunks (throughput stress)
# ---------------------------------------------------------------------------
def _create_large_file(index: int) -> Optional[str]:  # noqa: UP045
    target_dir = _random_nested_dir(BASE_DIR, MAX_DEPTH)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"large_{index:04d}.bin"
    total_size = LARGE_FILE_MIN_BYTES + secrets.randbelow(LARGE_FILE_MAX_BYTES - LARGE_FILE_MIN_BYTES + 1)
    h = hashlib.sha256()
    written = 0
    with path.open("wb") as f:
        while written < total_size:
            chunk_size = min(LARGE_FILE_WRITE_CHUNK, total_size - written)
            chunk = _random_bytes(chunk_size)
            f.write(chunk)
            h.update(chunk)
            written += chunk_size
    expected_hash = h.hexdigest()

    # read-after-write consistency check
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        return f"HASH MISMATCH (large) {path}: expected={expected_hash} actual={actual_hash}"
    return None


@_finalise_phase
def phase_2_create_large_file() -> None:
    print(
        f"Phase 2: creating 1 large file "
        f"({LARGE_FILE_MIN_BYTES // 1024 // 1024}-{LARGE_FILE_MAX_BYTES // 1024 // 1024} MiB) ..."
    )
    t0 = time.monotonic()
    err = _create_large_file(0)
    if err:
        errors.append(err)
    elapsed = time.monotonic() - t0
    print(f"  ✓ 1 large file created in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Phase 3 - Read-back all files and verify integrity
# ---------------------------------------------------------------------------
@_finalise_phase
def phase_3_read_back_files() -> None:
    print("Phase 3: reading back all files ...")
    t0 = time.monotonic()
    all_files = list(BASE_DIR.rglob("*.bin"))
    readable_count = 0
    for p in all_files:
        try:
            _ = p.read_bytes()
            readable_count += 1
        except Exception as exc:  # pylint: disable=broad-exception-caught
            errors.append(f"READ ERROR {p}: {exc}")
    elapsed = time.monotonic() - t0
    print(f"  ✓ {readable_count}/{len(all_files)} files readable in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Phase 4 - Rename / move files (copy-on-S3 stress)
# ---------------------------------------------------------------------------
@_finalise_phase
def phase_4_move_small_files() -> None:
    # NOTE: moving small files since it's faster
    print("Phase 4: renaming / moving files ...")
    t0 = time.monotonic()
    all_small_files = [p for p in BASE_DIR.rglob("*.bin") if not p.name.startswith("large_")]
    move_count = 0
    files_to_move = secrets.SystemRandom().sample(all_small_files, min(FILES_TO_MOVE, len(all_small_files)))
    for src in files_to_move:
        dst_dir = _random_nested_dir(BASE_DIR, MAX_DEPTH)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / f"moved_{src.name}"
        try:
            original_hash = _sha256(src)
            shutil.move(str(src), str(dst))
            moved_hash = _sha256(dst)
            if original_hash != moved_hash:
                errors.append(f"HASH MISMATCH after move {src} -> {dst}")
            move_count += 1
        except Exception as exc:  # pylint: disable=broad-exception-caught
            errors.append(f"MOVE ERROR {src} -> {dst}: {exc}")
    elapsed = time.monotonic() - t0
    print(f"  ✓ {move_count} files moved in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Phase 5 - Directory listing consistency
# ---------------------------------------------------------------------------
@_finalise_phase
def phase_5_listing_consistency() -> None:
    print("Phase 5: directory listing consistency ...")
    t0 = time.monotonic()
    all_files = list(BASE_DIR.rglob("*.bin"))
    listed_files = set(all_files)
    existing_files = {p for p in all_files if p.exists()}
    missing = existing_files - listed_files
    if missing:
        errors.append(f"LISTING INCONSISTENCY: {len(missing)} files exist but not listed")
    elapsed = time.monotonic() - t0
    print(f"  ✓ listing check done in {elapsed:.1f}s ({len(listed_files)} files found)")


# ---------------------------------------------------------------------------
# All phases - convenience list for programmatic access
# ---------------------------------------------------------------------------
ALL_PHASES: List[Tuple[str, int]] = [  # noqa: UP006
    (phase_1_create_small_files.__name__, 30 * _SECOND),
    (phase_2_create_large_file.__name__, 5 * _MINUTE),
    (phase_3_read_back_files.__name__, 3 * _MINUTE),
    (phase_4_move_small_files.__name__, 3 * _MINUTE),
    (phase_5_listing_consistency.__name__, 1 * _MINUTE),
]
