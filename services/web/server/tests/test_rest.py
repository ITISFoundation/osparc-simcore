# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import pytest
import yaml


from simcore_service_webserver import (
    resources,
    rest
)

async def test_apiversion():
    """
        Checks consistency between versionings
    """
    assert resources.exists(rest.settings.API_SPECS_NAME)

    specs = yaml.load(resources.stream(rest.settings.API_SPECS_NAME))

    api_version = specs['info']['version'].split(".")
    assert int(api_version[0]) == rest.settings.API_MAJOR_VERSION

    # TODO: follow https://semver.org/
    oas_version = [int(n) for n in specs['openapi'].split(".")]
    assert oas_version[0] == 3
    assert oas_version >= [3, 0, 0]
