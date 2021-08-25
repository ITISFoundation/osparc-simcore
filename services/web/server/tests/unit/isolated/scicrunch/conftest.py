# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
import sys
from pathlib import Path

import pytest
from simcore_service_webserver.scicrunch.submodule_setup import SciCrunchSettings


@pytest.fixture
async def settings(loop) -> SciCrunchSettings:
    return SciCrunchSettings(api_key=os.environ.get("SCICRUNCH_API_KEY", "FAKE"))
