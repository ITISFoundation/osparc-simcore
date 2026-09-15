# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import re
from pathlib import Path

import pytest

# Single source of truth for the uv version: requirements/UV_VERSION
#
# The version is pinned exactly due to https://github.com/astral-sh/uv/issues/21692
# (uv 0.12.14 rejects wheels carrying a .data payload when the install destination
# is a symlink, e.g. /usr/local/man in python:* images -> blosc fails to install).
# Unpin (or update the file) once fixed upstream.

UV_VERSION_DOCKER_PATTERN = re.compile(r'ARG UV_VERSION="?([\d][\d\.]*)"?')
# captures a literal pinned version (e.g. "0.12.13") in the 'version:' input that
# immediately follows an astral-sh/setup-uv step; expression-based values like
# ${{ steps.uv-version.outputs.version }} do not match (they resolve from the file)
SETUP_UV_VERSION_PATTERN = re.compile(
    r"astral-sh/setup-uv@[^\n]+\n\s+with:\s*\n\s+version:\s*\"([\d][\d\.]*)\"",
    re.MULTILINE,
)

# local build/dependency artifacts (e.g. old repo revisions inside .cache/uv git
# checkouts or site-packages) must not be scanned
_EXCLUDED_DIR_NAMES = {"node_modules", "__pycache__", ".venv", ".cache", ".git"}


def _is_scanned(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    return not any(part in _EXCLUDED_DIR_NAMES or part.startswith(".") for part in rel_parts)


@pytest.fixture(scope="session")
def expected_uv_version(osparc_simcore_root_dir: Path) -> str:
    uv_version = (osparc_simcore_root_dir / "requirements" / "UV_VERSION").read_text().strip()
    print("Expected uv", uv_version)
    return uv_version


def _dockerfiles_pinning_uv(osparc_simcore_root_dir: Path) -> list[tuple[Path, str]]:
    found = []
    for dockerfile_path in osparc_simcore_root_dir.rglob("Dockerfile"):
        if not _is_scanned(dockerfile_path, osparc_simcore_root_dir):
            continue
        if match := UV_VERSION_DOCKER_PATTERN.search(dockerfile_path.read_text()):
            version = match.group(1)
            print(str(dockerfile_path.relative_to(osparc_simcore_root_dir)), "->", version)
            found.append((dockerfile_path, version))
    assert found
    return found


def _workflows_pinning_uv(osparc_simcore_root_dir: Path) -> list[tuple[Path, str]]:
    found = []
    for workflow_path in (osparc_simcore_root_dir / ".github" / "workflows").glob("*.yml"):
        content = workflow_path.read_text()
        if "astral-sh/setup-uv" not in content:
            continue
        # only literal pins need checking; steps resolving requirements/UV_VERSION
        # (via a "resolve uv version" step output) are the source of truth already
        for match in SETUP_UV_VERSION_PATTERN.finditer(content):
            version = match.group(1)
            print(str(workflow_path.relative_to(osparc_simcore_root_dir)), "->", version)
            found.append((workflow_path, version))
    return found


def test_all_dockerfiles_have_the_same_uv_version(osparc_simcore_root_dir: Path, expected_uv_version: str):
    for dockerfile, uv_version in _dockerfiles_pinning_uv(osparc_simcore_root_dir):
        assert uv_version == expected_uv_version, (
            f"Expected uv {expected_uv_version} in {dockerfile}, got {uv_version}."
            " Update it to match requirements/UV_VERSION"
            " (see https://github.com/astral-sh/uv/issues/21692 for why it is pinned)."
        )


def test_all_workflows_have_the_same_uv_version(osparc_simcore_root_dir: Path, expected_uv_version: str):
    for workflow, uv_version in _workflows_pinning_uv(osparc_simcore_root_dir):
        assert uv_version == expected_uv_version, (
            f"Expected uv {expected_uv_version} in {workflow}, got {uv_version}."
            " Update it to match requirements/UV_VERSION"
            " or resolve the version from that file with a 'resolve uv version' step."
        )
