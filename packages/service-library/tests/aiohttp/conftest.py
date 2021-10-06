# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

import pytest
from faker import Faker
from servicelib.aiohttp.openapi import OpenApiSpec, create_openapi_specs


@pytest.fixture
def petstore_spec_file(here) -> Path:
    filepath = here / "data/oas3/petstore.yaml"
    assert filepath.exists()
    return filepath


@pytest.fixture
async def petstore_specs(loop, petstore_spec_file) -> OpenApiSpec:
    specs = await create_openapi_specs(petstore_spec_file)
    return specs


@pytest.fixture
def fake_data_dict(faker: Faker) -> Dict[str, Any]:
    data = {
        "uuid": uuid4(),
        "int": faker.pyint(),
        "float": faker.pyfloat(),
        "str": faker.pystr(),
    }
    data["object"] = deepcopy(data)
    return data
