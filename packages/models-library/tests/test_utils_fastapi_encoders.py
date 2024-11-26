# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from uuid import uuid4

from common_library.json_serialization import json_dumps
from faker import Faker
from models_library.utils.fastapi_encoders import servicelib_jsonable_encoder


def test_using_uuids_as_keys(faker: Faker):
    uuid_key = uuid4()

    # this was previously failing
    assert json_dumps({uuid_key: "value"}, indent=1)

    # uuid keys now serialize without raising to the expected format string
    data = servicelib_jsonable_encoder({uuid_key: "value"})
    assert data == {f"{uuid_key}": "value"}

    # serialize w/o raising
    dumped_data = json_dumps(data, indent=1)

    # deserialize w/o raising
    loaded_data = json.loads(dumped_data)

    # no data loss
    assert data == loaded_data
