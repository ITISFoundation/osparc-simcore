# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import re
from pathlib import Path

import pytest
import yaml
from pytest_simcore.helpers.stack_names import (
    MAX_STACK_NAME_LEN,
    compute_stack_names,
    get_checkout_token,
    get_checkout_uid,
    get_git_ref,
)

_DOCKER_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# two checkouts of the same repo, e.g. the main clone and a git worktree
_CHECKOUT_A = Path("/home/dev/simcore")
_CHECKOUT_B = Path("/home/dev/simcore-worktree")


def test_names_are_docker_legal_and_bounded():
    core, ops = compute_stack_names("maintenance/fix-something", get_checkout_token(_CHECKOUT_A))
    assert core.startswith("pytest-")
    assert ops.startswith("pytest-")
    assert ops.endswith("-ops")
    for name in (core, ops):
        assert len(name) <= MAX_STACK_NAME_LEN
        assert _DOCKER_NAME_PATTERN.match(name), name


def test_branch_fragment_is_recognizable_and_sanitized():
    core, _ = compute_stack_names("fix/Fix_Autoscaling.Reqs", get_checkout_token(_CHECKOUT_A))
    assert "fix-fix-autoscaling" in core


def test_long_branch_is_truncated_to_budget():
    core, ops = compute_stack_names("maintenance/fix-autoscaling-reqs-and-more" * 3, get_checkout_token(_CHECKOUT_A))
    # the branch fragment keeps its prefix (still recognizable) and the name fits
    assert core.startswith("pytest-maintenance-fix-autos-")
    assert len(core) <= MAX_STACK_NAME_LEN
    assert len(ops) <= MAX_STACK_NAME_LEN


def test_same_branch_in_different_checkouts_does_not_collide():
    core_a, ops_a = compute_stack_names("master", get_checkout_token(_CHECKOUT_A))
    core_b, ops_b = compute_stack_names("master", get_checkout_token(_CHECKOUT_B))
    assert core_a != core_b
    assert ops_a != ops_b


def test_names_are_stable_across_runs_of_one_checkout():
    # only the checkout enters the name, so a second run of the same checkout lands on the
    # same stacks -- what makes a stack kept up by '--keep-docker-up' get reused
    first_run = compute_stack_names("master", get_checkout_token(_CHECKOUT_A))
    second_run = compute_stack_names("master", get_checkout_token(_CHECKOUT_A))
    assert first_run == second_run


def test_missing_branch_still_produces_unique_names():
    core1, _ = compute_stack_names("", get_checkout_token(_CHECKOUT_A))
    core2, _ = compute_stack_names("", get_checkout_token(_CHECKOUT_B))
    assert core1 != core2
    assert _DOCKER_NAME_PATTERN.match(core1)


def test_checkout_uid_is_short_and_stable(tmp_path: Path):
    assert get_checkout_token(tmp_path) == f"{tmp_path.resolve()}"
    uid = get_checkout_uid(tmp_path)
    assert re.fullmatch(r"[0-9a-f]{4}", uid)
    # the same checkout written differently is still the same checkout
    assert get_checkout_uid(tmp_path / "services" / "..") == uid


def test_checkout_token_is_stable_when_reached_through_a_symlink(tmp_path: Path):
    checkout = tmp_path / "simcore"
    checkout.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(checkout, target_is_directory=True)
    assert get_checkout_token(alias) == get_checkout_token(checkout)


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
def test_longest_deployed_name_fits_dns_label(osparc_simcore_root_dir: Path, compose_filename: str):
    """the DNS budget baked into MAX_STACK_NAME_LEN must cover every deployed name

    "docker stack deploy" prefixes both services and networks with "{stack}_", so both
    compete for the same 63-char DNS-label budget.
    """
    compose_path = osparc_simcore_root_dir / "services" / compose_filename
    compose = yaml.safe_load(compose_path.read_text())

    deployed_names = [*(compose.get("services") or {}), *(compose.get("networks") or {})]
    longest = max((len(name) for name in deployed_names), default=0)
    assert longest > 0
    # NOTE: 63 = limit of a single DNS label (RFC 1123)
    assert MAX_STACK_NAME_LEN + len("_") + longest <= 63
