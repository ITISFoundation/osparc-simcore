# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from simcore_service_webserver.scicrunch.settings import SciCrunchSettings


@pytest.fixture
async def settings() -> SciCrunchSettings:
    return SciCrunchSettings(SCICRUNCH_API_KEY="fake-secret-key")
