# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import re
from pathlib import Path

import pytest
import yaml
from pytest_simcore.helpers.stack_names import (
    MAX_STACK_NAME_LEN,
    compute_stack_names,
    get_git_ref,
    get_run_token,
    get_run_uid,
)

_DOCKER_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


_RUN_DIR = Path("pytest-run-dirs/pytest-1")


def test_names_are_docker_legal_and_bounded():
    core, ops = compute_stack_names("maintenance/fix-something", f"{_RUN_DIR}")
    assert core.startswith("pytest-")
    assert ops.startswith("pytest-")
    assert ops.endswith("-ops")
    for name in (core, ops):
        assert len(name) <= MAX_STACK_NAME_LEN
        assert _DOCKER_NAME_PATTERN.match(name), name


def test_branch_fragment_is_recognizable_and_sanitized():
    core, _ = compute_stack_names("fix/Fix_Autoscaling.Reqs", f"{_RUN_DIR}")
    assert "fix-fix-autoscaling-reqs" in core


def test_long_branch_is_truncated_to_budget():
    core, ops = compute_stack_names("maintenance/fix-autoscaling-reqs-and-more" * 3, f"{_RUN_DIR}")
    # the branch fragment keeps its prefix (still recognizable) and the name fits
    assert core.startswith("pytest-maintenance-fix-autoscal-")
    assert len(core) <= MAX_STACK_NAME_LEN
    assert len(ops) <= MAX_STACK_NAME_LEN


def test_same_branch_different_runs_do_not_collide():
    core_a, ops_a = compute_stack_names("master", f"{_RUN_DIR}")
    core_b, ops_b = compute_stack_names("master", f"{_RUN_DIR.parent}/pytest-2")
    assert core_a != core_b
    assert ops_a != ops_b


def test_names_are_stable_within_a_run():
    core1, ops1 = compute_stack_names("master", f"{_RUN_DIR}")
    core2, ops2 = compute_stack_names("master", f"{_RUN_DIR}")
    assert (core1, ops1) == (core2, ops2)


def test_missing_branch_still_produces_unique_names():
    core1, _ = compute_stack_names("", f"{_RUN_DIR}")
    core2, _ = compute_stack_names("", f"{_RUN_DIR.parent}/pytest-2")
    assert core1 != core2
    assert _DOCKER_NAME_PATTERN.match(core1)


@pytest.mark.parametrize(
    "basetemp,expected",
    [
        # plain run: the base temp dir IS the run dir
        (_RUN_DIR, _RUN_DIR),
        # xdist worker: the shared run dir is the parent of the worker's base temp dir
        (_RUN_DIR / "popen-gw3", _RUN_DIR),
    ],
)
def test_run_token_shared_across_xdist_workers_of_one_run(basetemp: Path, expected: Path):
    assert get_run_token(basetemp) == f"{expected}"
    # every worker of the same run computes the same token
    other_worker = expected / "popen-gw9"
    assert get_run_token(other_worker) == get_run_token(basetemp)
    # ... and the same readable run uid
    assert get_run_uid(other_worker) == get_run_uid(basetemp) == expected.name


def test_get_git_ref_falls_back_without_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent")
    assert get_git_ref(tmp_path) == "local"


def test_get_git_ref_prefers_github_head_ref(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_HEAD_REF", "some/pr-branch")
    monkeypatch.setenv("GITHUB_REF_NAME", "123/merge")
    assert get_git_ref(tmp_path) == "some/pr-branch"


def test_get_git_ref_uses_github_ref_name_on_push_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_REF_NAME", "master")
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    assert get_git_ref(tmp_path) == "master"


@pytest.mark.parametrize("compose_filename", ["docker-compose.yml", "docker-compose-ops.yml"])
def test_longest_stack_service_alias_fits_dns_label(osparc_simcore_root_dir: Path, compose_filename: str):
    """the DNS budget baked into MAX_STACK_NAME_LEN must cover every deployed service"""
    compose_path = osparc_simcore_root_dir / "services" / compose_filename
    services = yaml.safe_load(compose_path.read_text())["services"]

    longest = max((len(name) for name in services), default=0)
    assert longest > 0
    # NOTE: 63 = limit of a single DNS label (RFC 1123)
    assert MAX_STACK_NAME_LEN + len("_") + longest <= 63
