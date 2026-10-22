# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import re
from pathlib import Path
from typing import Final

import pytest
import yaml
from pytest_simcore.helpers.stack_names import (
    MAX_STACK_NAME_LEN,
    compute_stack_names,
    get_checkout_token,
    get_checkout_uid,
    get_git_ref,
    get_slot_stack_prefix,
    is_service_in_stack,
)

_DOCKER_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def test_names_carry_slot_branch_and_role():
    assert compute_stack_names(3, "maintenance/fix") == (
        "pytest-s3-maintenance-fix-core",
        "pytest-s3-maintenance-fix-ops",
    )


@pytest.mark.parametrize("slot", [0, 9])
@pytest.mark.parametrize("git_ref", ["master", "fix/Fix_AutoScal", "maintenance/fix-autoscaling-reqs-and-more" * 3, ""])
def test_names_are_docker_legal_bounded_and_in_the_slot(slot: int, git_ref: str):
    for name in compute_stack_names(slot, git_ref):
        assert len(name) <= MAX_STACK_NAME_LEN
        assert _DOCKER_NAME_PATTERN.match(name), name
        assert name.startswith(get_slot_stack_prefix(slot))


def test_long_branch_is_cut_in_the_middle():
    core, ops = compute_stack_names(1, "maintenance/fix-autoscaling-reqs-and-more" * 3)

    branch = core.removeprefix("pytest-s1-").removesuffix("-core")
    assert branch.startswith("maintenan")
    assert branch.endswith("and-more")
    assert ops == f"pytest-s1-{branch}-ops"


def test_missing_branch_keeps_slot_and_role():
    assert compute_stack_names(2, "") == ("pytest-s2-core", "pytest-s2-ops")


def test_slot_prefixes_do_not_overlap():
    prefixes = [get_slot_stack_prefix(slot) for slot in range(10)]
    for prefix in prefixes:
        assert [other for other in prefixes if other.startswith(prefix)] == [prefix]


def test_is_service_in_stack_requires_the_full_stack_prefix():
    assert is_service_in_stack("pytest-core-one-1234_postgres", "pytest-core-one-1234")
    # a co-tenant stack whose name merely extends ours must not be mistaken for it
    assert not is_service_in_stack("pytest-core-one-12345_postgres", "pytest-core-one-1234")
    assert not is_service_in_stack("other-core-1234_postgres", "pytest-core-one-1234")


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
