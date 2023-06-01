import pytest
from faker import Faker
from models_library.basic_types import UUIDStr
from pydantic import ValidationError
from pydantic.tools import parse_obj_as


@pytest.mark.skip(reason="DEV: testing parse_obj_as")
def test_parse_uuid_as_a_string(faker: Faker):
    expected_uuid = faker.uuid4()
    got_uuid = parse_obj_as(UUIDStr, expected_uuid)

    assert isinstance(got_uuid, str)
    assert got_uuid == expected_uuid

    with pytest.raises(ValidationError):
        parse_obj_as(UUIDStr, "123456-is-not-an-uuid")
