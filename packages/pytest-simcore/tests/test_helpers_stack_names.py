# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import re
from pathlib import Path

import pytest
import yaml
from pytest_simcore.helpers.stack_names import (
    MAX_STACK_NAME_LEN,
    get_checkout_token,
    get_checkout_uid,
    is_service_in_stack,
)


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
