# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re

import pytest
from service_integration import __version__
from service_integration._meta import INTEGRATION_API_VERSION, project_name
from service_integration.basic_regex import (
    PEP404_VERSION_RE,
    SEMANTIC_VERSION_RE,
    VERSION_RE,
)


def test_package_metadata():
    assert project_name == "simcore-service-integration"


@pytest.mark.parametrize("version", [__version__, INTEGRATION_API_VERSION])
def test_package_metadata_versions(version):

    # is semantic?
    assert re.match(
        SEMANTIC_VERSION_RE, version
    ), f"{version} is invalid semantic version"

    # regex used in model valiation
    assert re.match(VERSION_RE, version), f"{version} is invalid version"

    # pep404 ?
    assert re.match(PEP404_VERSION_RE, version), f"{version} is invalid PEP404 version"
