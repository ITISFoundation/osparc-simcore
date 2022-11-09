# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from typing import Any
from uuid import uuid4

import pytest
from faker import Faker
from models_library.utils.fastapi_encoders import servicelib_jsonable_encoder
from pydantic.json import pydantic_encoder


def servicelib__json_serialization__json_dumps(obj: Any, **kwargs):
    # Analogous to 'servicelib.json_serialization.json_dumps'
    return json.dumps(obj, default=pydantic_encoder, **kwargs)


def test_using_uuids_as_keys(faker: Faker):

    uuid_key = uuid4()

    with pytest.raises(TypeError):
        # IMPORTANT NOTE: we cannot serialize UUID objects as keys.
        # We have to convert them to strings but then the class information is lost upon deserialization i.e. it is not reversable!
        # NOTE: This could  potentially be solved using 'orjson' !!
        #
        servicelib__json_serialization__json_dumps({uuid_key: "value"}, indent=1)

    # use encoder
    data = servicelib_jsonable_encoder({uuid_key: "value"})
    assert data == {f"{uuid_key}": "value"}

    # serialize w/o raising
    dumped_data = servicelib__json_serialization__json_dumps(data, indent=1)

    # deserialize w/o raising
    loaded_data = json.loads(dumped_data)

    # no data loss
    assert data == loaded_data
