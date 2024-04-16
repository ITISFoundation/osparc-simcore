# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from typing import Any
from uuid import uuid4

import pytest
from models_library.utils.fastapi_encoders import jsonable_encoder
from servicelib.json_serialization import OrJsonAdapter, json_dumps


def test_json_dump_variants():

    uuid_obj = uuid4()

    with pytest.raises(TypeError) as exc_info:
        json.dumps(uuid_obj)

    assert str(exc_info.value) == "Object of type UUID is not JSON serializable"

    assert json_dumps(uuid_obj) == json.dumps(str(uuid_obj))


def test_serialization_of_uuids(fake_data_dict: dict[str, Any]):
    # NOTE: UUIDS serialization/deserialization is asymetric.
    # We should eventually fix this but adding a corresponding decoder?

    uuid_obj = uuid4()
    # NOTE the quotes around expected value
    assert json_dumps(uuid_obj) == f'"{uuid_obj}"'

    obj = {"ids": [uuid4() for _ in range(3)]}
    dump = json_dumps(obj)

    # NOTE: UUIDs are deserialized as strings, therefore we need to use jsonable_encoder
    assert json.loads(dump) == jsonable_encoder(obj)


def test_serialization_of_nested_dicts(fake_data_dict: dict[str, Any]):

    obj = {"data": fake_data_dict, "ids": [uuid4() for _ in range(3)]}

    dump = json_dumps(obj)
    # NOTE: UUIDs are deserialized as strings, therefore we need to use jsonable_encoder
    assert json.loads(dump) == jsonable_encoder(obj)


def test_orjson_adapter(fake_data_dict: dict[str, Any]):
    dump = OrJsonAdapter.dumps(fake_data_dict)
    # NOTE: UUIDs are deserialized as strings, therefore we need to use jsonable_encoder
    assert OrJsonAdapter.loads(dump) == jsonable_encoder(fake_data_dict)
