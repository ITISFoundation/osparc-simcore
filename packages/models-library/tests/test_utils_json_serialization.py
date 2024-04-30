# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from typing import Any
from uuid import uuid4

import pytest
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


def test_orjson_adapter_has_dumps_interface(fake_data_dict: dict[str, Any]):

    assert JsonNamespace.dumps(fake_data_dict) == _expected_json_dumps(fake_data_dict)

    sort_keys = True
    assert JsonNamespace.dumps(
        fake_data_dict, sort_keys=sort_keys
    ) == _expected_json_dumps(fake_data_dict, sort_keys=sort_keys)

    # NOTE: e.g. engineio.packet has `self.json.dumps(self.data, separators=(',', ':'))`
    separators = ",", ":"
    assert JsonNamespace.dumps(
        fake_data_dict, separators=separators
    ) == _expected_json_dumps(fake_data_dict, separators=separators)

    separators = " , ", " : "
    assert JsonNamespace.dumps(
        fake_data_dict, separators=separators
    ) == _expected_json_dumps(fake_data_dict, separators=separators)

    # NOTE: only one-to-one with indent=2
    indent = 2
    assert JsonNamespace.dumps(fake_data_dict, indent=indent) == _expected_json_dumps(
        fake_data_dict, indent=indent
    )


def test_serialized_non_str_dict_keys():
    # tests orjson.OPT_NON_STR_KEYS option

    # if a dict has a key of a type other than str it will NOT raise
    json_dumps({1: "foo"})


def test_serialized_constraint_floats():
    # test extension of ENCODERS_BY_TYPE used in pydantic_encoder

    json_dumps({"value": 1.0})

    # TypeError: Type is not JSON serializable: ProgressPercent
    json_dumps({"value": ProgressPercent(1.0)})
