# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from copy import deepcopy
from typing import Any
from uuid import uuid4

import pytest
from common_library.json_serialization import json_dumps, json_loads
from faker import Faker
from models_library.utils.fastapi_encoders import jsonable_encoder


@pytest.fixture
def fake_data_dict(faker: Faker) -> dict[str, Any]:
    data = {
        "uuid_as_UUID": faker.uuid4(cast_to=None),
        "uuid_as_str": faker.uuid4(),
        "int": faker.pyint(),
        "float": faker.pyfloat(),
        "str": faker.pystr(),
        "dict": faker.pydict(),
        "list": faker.pylist(),
    }
    data["object"] = deepcopy(data)
    return data


def test_serialization_of_uuids(fake_data_dict: dict[str, Any]):
    # NOTE: UUIDS serialization/deserialization is asymetric.
    # We should eventually fix this but adding a corresponding decoder?

    uuid_obj = uuid4()
    assert json_dumps(uuid_obj) == f'"{uuid_obj}"'

    obj = {"ids": [uuid4() for _ in range(3)]}
    dump = json_dumps(obj)
    assert json_loads(dump) == jsonable_encoder(obj)


def test_serialization_of_nested_dicts(fake_data_dict: dict[str, Any]):

    obj = {"data": fake_data_dict, "ids": [uuid4() for _ in range(3)]}

    dump = json_dumps(obj)
    assert json_loads(dump) == jsonable_encoder(obj)
