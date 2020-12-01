# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from pkg_resources import parse_version
from service_integration.version_utils import bump_version_string

# TESTS ------------------------------------------


def test_pep404_compare_versions():
    # TODO: replace pkg_resources with https://importlib-metadata.readthedocs.io/en/latest/index.html so it is standard in 3.8

    # A reminder from https://setuptools.readthedocs.io/en/latest/userguide/distribution.html#specifying-your-project-s-version
    assert parse_version("1.9.a.dev") == parse_version("1.9a0dev")
    assert parse_version("2.1-rc2") < parse_version("2.1")
    assert parse_version("0.6a9dev-r41475") < parse_version("0.6a9")

    # same release but one is pre-release
    assert (
        parse_version("2.1-rc2").release == parse_version("2.1").release
        and parse_version("2.1-rc2").is_prerelease
    )


BUMP_PARAMS = [
    # "upgrade,current_version,new_version",
    ("patch", "1.1.1", "1.1.2"),
    ("minor", "1.1.1", "1.2.0"),
    ("major", "1.1.1", "2.0.0"),
]


@pytest.mark.parametrize(
    "bump,current_version,new_version",
    BUMP_PARAMS,
)
def test_bump_version_string(
    bump: str,
    current_version: str,
    new_version: str,
):
    assert bump_version_string(current_version, bump) == new_version
