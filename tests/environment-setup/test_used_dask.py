# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import re
import tomllib
from pathlib import Path

import pytest

# autoscaled-monitor is a dask client: it talks to the cluster with the very same dask
# version the dask-sidecar runs (see the NOTE in its pyproject.toml)
AUTOSCALED_MONITOR_DIR = Path("scripts/maintenance/autoscaled-monitor")
DASK_SIDECAR_REQUIREMENTS = Path("services/dask-sidecar/requirements/_dask-distributed.txt")

_DASK_REQUIREMENT = re.compile(r"dask(?:\[[^\]]*\])?==(?P<version>[^,;\s]+)")
_DASK_PIN = re.compile(r"^dask==(?P<version>[^\s#]+)", re.MULTILINE)
_DISTRIBUTED_PIN = re.compile(r"^distributed==(?P<version>[^\s#]+)", re.MULTILINE)


def _pinned_version(pattern: re.Pattern[str], text: str, source: str) -> str:
    match = pattern.search(text)
    assert match is not None, f"{source} is expected to pin dask with '=='."
    return match["version"]


@pytest.fixture(scope="session")
def expected_dask_version(osparc_simcore_root_dir: Path) -> str:
    """The dask version the computational cluster runs"""
    requirements = (osparc_simcore_root_dir / DASK_SIDECAR_REQUIREMENTS).read_text()
    source = str(DASK_SIDECAR_REQUIREMENTS)
    dask = _pinned_version(_DASK_PIN, requirements, source)
    distributed = _pinned_version(_DISTRIBUTED_PIN, requirements, source)
    print("Expected dask", dask)
    assert dask == distributed, (
        f"{source} pins dask {dask} and distributed {distributed}."
        " The scheduler and the workers run the same version, run 'make requirements' in services/dask-sidecar."
    )
    return dask


def _pyproject_dask_version(osparc_simcore_root_dir: Path) -> str:
    pyproject_path = AUTOSCALED_MONITOR_DIR / "pyproject.toml"
    pyproject = tomllib.loads((osparc_simcore_root_dir / pyproject_path).read_text())
    pinned = [dependency for dependency in pyproject["project"]["dependencies"] if _DASK_REQUIREMENT.search(dependency)]
    assert len(pinned) == 1, f"{pyproject_path} is expected to pin dask exactly once, got {pinned}."
    return _pinned_version(_DASK_REQUIREMENT, pinned[0], str(pyproject_path))


def _uv_lock_dask_version(osparc_simcore_root_dir: Path) -> str:
    lock_path = AUTOSCALED_MONITOR_DIR / "uv.lock"
    lock = tomllib.loads((osparc_simcore_root_dir / lock_path).read_text())
    versions = {package["version"] for package in lock["package"] if package["name"] == "dask"}
    assert len(versions) == 1, f"{lock_path} is expected to resolve dask exactly once, got {versions}."
    return versions.pop()


def test_autoscaled_monitor_pins_the_dask_sidecar_version(osparc_simcore_root_dir: Path, expected_dask_version: str):
    dask = _pyproject_dask_version(osparc_simcore_root_dir)
    assert dask == expected_dask_version, (
        f"Expected dask {expected_dask_version} in {AUTOSCALED_MONITOR_DIR}/pyproject.toml, got {dask}."
        f" Run 'make sync-dask-version' in {AUTOSCALED_MONITOR_DIR}."
        " On a Renovate pull request it is .github/renovate/sync_autoscaled_monitor_dask.py that"
        " should have done it, so look for its section in renovate-resync-report.md."
    )


def test_autoscaled_monitor_locks_the_dask_sidecar_version(osparc_simcore_root_dir: Path, expected_dask_version: str):
    dask = _uv_lock_dask_version(osparc_simcore_root_dir)
    assert dask == expected_dask_version, (
        f"Expected dask {expected_dask_version} in {AUTOSCALED_MONITOR_DIR}/uv.lock, got {dask}."
        f" Run 'make sync-dask-version' in {AUTOSCALED_MONITOR_DIR}."
        " On a Renovate pull request, run it again once its post-upgrade task did."
    )
