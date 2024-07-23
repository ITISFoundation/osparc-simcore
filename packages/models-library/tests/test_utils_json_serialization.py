# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from copy import deepcopy
from typing import Any
from uuid import uuid4

import pytest
from faker import Faker
from models_library.api_schemas_long_running_tasks.base import ProgressPercent
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.utils.json_serialization import (
    JsonNamespace,
    SeparatorTuple,
    json_dumps,
    json_loads,
)
from pydantic.json import pydantic_encoder


def _expected_json_dumps(obj: Any, default=pydantic_encoder, **json_dumps_kwargs):
    if "indent" not in json_dumps_kwargs:
        json_dumps_kwargs.setdefault(
            "separators",
            SeparatorTuple(item_separator=",", key_separator=":"),  # compact separators
        )
    return json.dumps(obj, default=default, **json_dumps_kwargs)


def test_json_dump_variants():

    uuid_obj = uuid4()

    with pytest.raises(TypeError) as exc_info:
        json.dumps(uuid_obj)

    assert str(exc_info.value) == "Object of type UUID is not JSON serializable"

    assert json_dumps(uuid_obj) == json.dumps(str(uuid_obj))


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


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({}, id="no-kw"),
        pytest.param({"sort_keys": True}, id="sort_keys-kw"),
        pytest.param(
            {"separators": (",", ":")}, id="default_separators-kw"
        ),  # NOTE: e.g. engineio.packet has `self.json.dumps(self.data, separators=(',', ':'))`
        pytest.param(
            {"indent": 2}, id="indent-kw"
        ),  # NOTE: only one-to-one with indent=2
    ],
)
def test_compatiblity_with_json_interface(
    fake_data_dict: dict[str, Any], kwargs: dict[str, Any]
):
    orjson_dump = JsonNamespace.dumps(fake_data_dict, **kwargs)
    json_dump = _expected_json_dumps(fake_data_dict, **kwargs)

    # NOTE: cannot compare dumps directly because orjson compacts it more
    assert json_loads(orjson_dump) == json_loads(json_dump)


def test_serialized_non_str_dict_keys():
    # tests orjson.OPT_NON_STR_KEYS option

    # if a dict has a key of a type other than str it will NOT raise
    json_dumps({1: "foo"})


def test_serialized_constraint_floats():
    # test extension of ENCODERS_BY_TYPE used in pydantic_encoder

    json_dumps({"value": 1.0})

    # TypeError: Type is not JSON serializable: ProgressPercent
    json_dumps({"value": ProgressPercent(1.0)})
