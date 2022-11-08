# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re

import pytest
from models_library.basic_regex import SEMANTIC_VERSION_RE_W_NAMED_GROUPS
from packaging.version import Version
from service_integration import __version__
from service_integration._meta import INTEGRATION_API_VERSION, project_name


def test_package_metadata():
    assert project_name == "simcore-service-integration"


@pytest.mark.parametrize("version", [__version__, INTEGRATION_API_VERSION])
def test_package_metadata_versions(version):

    assert re.match(
        SEMANTIC_VERSION_RE_W_NAMED_GROUPS, version
    ), f"{version} is invalid semantic version"

    assert Version(version)
