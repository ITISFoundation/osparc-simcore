# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from pathlib import Path

import pytest
from servicelib.aiohttp.openapi import OpenApiSpec, create_openapi_specs


@pytest.fixture
def petstore_spec_file(here) -> Path:
    filepath = here / "data/oas3/petstore.yaml"
    assert filepath.exists()
    return filepath


@pytest.fixture
async def petstore_specs(petstore_spec_file) -> OpenApiSpec:
    specs = await create_openapi_specs(petstore_spec_file)
    return specs
