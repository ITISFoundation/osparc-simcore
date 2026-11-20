# pylint: disable=redefined-outer-name

import hashlib
from pathlib import Path
from typing import Final

import pytest
from simcore_service_dynamic_sidecar.modules.outputs._fingerprinter import (
    PortContentFingerprinter,
)

_PORT_KEY: Final[str] = "output_1"
_REQUIRED_STABLE_LOOKS: Final[int] = 5


@pytest.fixture
def fingerprinter() -> PortContentFingerprinter:
    return PortContentFingerprinter(required_stable_looks=_REQUIRED_STABLE_LOOKS)


@pytest.fixture
def port_dir(tmp_path: Path) -> Path:
    path = tmp_path / _PORT_KEY
    path.mkdir()
    return path


async def test_port_with_unchanging_content_settles_after_required_looks(
    fingerprinter: PortContentFingerprinter, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")

    first = await fingerprinter.observe(_PORT_KEY, port_dir)
    assert first.has_changed
    assert not first.is_settled

    for _ in range(_REQUIRED_STABLE_LOOKS - 1):
        status = await fingerprinter.observe(_PORT_KEY, port_dir)
        assert not status.is_settled

    final = await fingerprinter.observe(_PORT_KEY, port_dir)
    assert final.is_settled


async def test_content_change_resets_the_settling(fingerprinter: PortContentFingerprinter, port_dir: Path):
    (port_dir / "a.dat").write_bytes(b"hello")
    for _ in range(_REQUIRED_STABLE_LOOKS):
        await fingerprinter.observe(_PORT_KEY, port_dir)

    (port_dir / "a.dat").write_bytes(b"grew while being watched")
    after_change = await fingerprinter.observe(_PORT_KEY, port_dir)
    assert after_change.has_changed
    assert not after_change.is_settled


async def test_matches_last_upload_only_after_a_recorded_upload(
    fingerprinter: PortContentFingerprinter, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")
    for _ in range(_REQUIRED_STABLE_LOOKS):
        status = await fingerprinter.observe(_PORT_KEY, port_dir)
    assert not status.matches_last_upload

    recorded = await fingerprinter.note_upload_succeeded(_PORT_KEY, port_dir)
    assert recorded is True

    status = await fingerprinter.observe(_PORT_KEY, port_dir)
    assert status.matches_last_upload


async def test_upload_of_content_that_changed_during_upload_is_not_recorded(
    fingerprinter: PortContentFingerprinter, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")
    for _ in range(_REQUIRED_STABLE_LOOKS):
        await fingerprinter.observe(_PORT_KEY, port_dir)

    (port_dir / "a.dat").write_bytes(b"grew during the put")
    recorded = await fingerprinter.note_upload_succeeded(_PORT_KEY, port_dir)
    assert recorded is False

    status = await fingerprinter.observe(_PORT_KEY, port_dir)
    assert not status.matches_last_upload
    assert not status.is_settled


async def test_missing_port_directory_is_a_stable_empty_state(fingerprinter: PortContentFingerprinter, tmp_path: Path):
    missing = tmp_path / "gone"
    first = await fingerprinter.observe(_PORT_KEY, missing)
    assert first.has_changed
    for _ in range(_REQUIRED_STABLE_LOOKS - 1):
        assert not (await fingerprinter.observe(_PORT_KEY, missing)).is_settled

    assert (await fingerprinter.observe(_PORT_KEY, missing)).is_settled
    assert await fingerprinter.note_upload_succeeded(_PORT_KEY, missing) is True
    assert (await fingerprinter.observe(_PORT_KEY, missing)).matches_last_upload


async def test_symlink_target_content_change_is_detected(
    fingerprinter: PortContentFingerprinter, port_dir: Path, tmp_path: Path
):
    outside = tmp_path / "target.dat"
    outside.write_bytes(b"v1")
    (port_dir / "link.dat").symlink_to(outside)
    for _ in range(_REQUIRED_STABLE_LOOKS):
        await fingerprinter.observe(_PORT_KEY, port_dir)

    outside.write_bytes(b"v2 written through the link")
    assert (await fingerprinter.observe(_PORT_KEY, port_dir)).has_changed


async def test_broken_symlink_is_observed_without_raising(fingerprinter: PortContentFingerprinter, port_dir: Path):
    (port_dir / "broken.dat").symlink_to(port_dir / "never existed")
    first = await fingerprinter.observe(_PORT_KEY, port_dir)
    assert first.has_changed
    second = await fingerprinter.observe(_PORT_KEY, port_dir)
    assert not second.has_changed


async def test_digest_cache_is_scoped_per_port(fingerprinter: PortContentFingerprinter, tmp_path: Path):
    port_1_dir = tmp_path / "port_1"
    port_2_dir = tmp_path / "port_2"
    port_1_dir.mkdir()
    port_2_dir.mkdir()

    # both ports hold "f.dat" with equal size: a shared cache key would collide
    (port_1_dir / "f.dat").write_bytes(b"AAAA")
    (port_2_dir / "f.dat").write_bytes(b"BBBB")

    await fingerprinter.observe(_PORT_KEY, port_1_dir)
    await fingerprinter.observe("output_2", port_2_dir)

    port_1_cache = fingerprinter._hash_cache[_PORT_KEY]  # noqa: SLF001
    assert port_1_cache["f.dat"].digest == hashlib.sha256(b"AAAA").hexdigest()
