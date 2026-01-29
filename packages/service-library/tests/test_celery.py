from types import NoneType
from typing import Annotated

# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
import pydantic
import pytest
from common_library.json_serialization import json_dumps
from faker import Faker
from pydantic import StringConstraints, TypeAdapter
from servicelib.celery.models import (
    OwnerMetadata,
    TaskUUID,
    Wildcard,
)

_faker = Faker()


class _TestOwnerMetadata(OwnerMetadata):
    string_: str
    int_: int
    bool_: bool
    none_: None
    uuid_: str


@pytest.fixture
def test_owner_metadata() -> dict[str, str | int | bool | None | list[str]]:
    data = {
        "string_": _faker.word(),
        "int_": _faker.random_int(),
        "bool_": _faker.boolean(),
        "none_": None,
        "uuid_": _faker.uuid4(),
        "owner": _faker.word().lower(),
    }
    _TestOwnerMetadata.model_validate(data)  # ensure it's valid
    return data


async def test_task_filter_serialization(
    test_owner_metadata: dict[str, str | int | bool | None | list[str]],
):
    task_filter = _TestOwnerMetadata.model_validate(test_owner_metadata)
    assert task_filter.model_dump() == test_owner_metadata


async def test_task_filter_sorting_key_not_serialized():
    class _OwnerMetadata(OwnerMetadata):
        a: int | Wildcard
        b: str | Wildcard

    owner_metadata = _OwnerMetadata.model_validate(
        {"a": _faker.random_int(), "b": _faker.word(), "owner": _faker.word().lower()}
    )
    task_uuid = TypeAdapter(TaskUUID).validate_python(_faker.uuid4())
    copy_owner_metadata = owner_metadata.model_dump()
    copy_owner_metadata.update({"task_uuid": f"{task_uuid}"})

    expected_key = ":".join([f"{k}={json_dumps(v)}" for k, v in sorted(copy_owner_metadata.items())])
    assert owner_metadata.model_dump_task_key(task_uuid=task_uuid) == expected_key


async def test_task_filter_task_uuid(
    test_owner_metadata: dict[str, str | int | bool | None | list[str]],
):
    task_filter = _TestOwnerMetadata.model_validate(test_owner_metadata)
    task_uuid = TypeAdapter(TaskUUID).validate_python(_faker.uuid4())
    task_key = task_filter.model_dump_task_key(task_uuid)
    assert OwnerMetadata.get_task_uuid(task_key=task_key) == task_uuid


async def test_owner_metadata_task_key_dump_and_validate():
    class MyModel(OwnerMetadata):
        int_: int
        bool_: bool
        str_: str
        float_: float
        none_: NoneType
        list_s: list[str]
        list_i: list[int]
        list_f: list[float]
        list_b: list[bool]

    mymodel = MyModel(
        int_=1,
        none_=None,
        bool_=True,
        str_="test",
        float_=1.0,
        owner="myowner",
        list_b=[True, False],
        list_f=[1.0, 2.0],
        list_i=[1, 2],
        list_s=["a", "b"],
    )
    task_uuid = TypeAdapter(TaskUUID).validate_python(_faker.uuid4())
    task_key = mymodel.model_dump_task_key(task_uuid)
    mymodel_recreated = MyModel.model_validate_task_key(task_key=task_key)
    assert mymodel_recreated == mymodel


@pytest.mark.parametrize(
    "bad_data",
    [
        {"foo": "bar:baz"},
        {"foo": "bar=baz"},
        {"foo:bad": "bar"},
        {"foo=bad": "bar"},
        {"foo": ":baz"},
        {"foo": "=baz"},
    ],
)
def test_task_filter_validator_raises_on_forbidden_chars(bad_data):
    with pytest.raises(pydantic.ValidationError):
        OwnerMetadata.model_validate(bad_data)


async def test_task_owner():
    class MyOwnerMetadata(OwnerMetadata):
        extra_field: str

    with pytest.raises(pydantic.ValidationError):
        MyOwnerMetadata(owner="", extra_field="value")

    with pytest.raises(pydantic.ValidationError):
        MyOwnerMetadata(owner="UPPER_CASE", extra_field="value")

    class MyNextFilter(OwnerMetadata):
        owner: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^the_task_owner$")]

    with pytest.raises(pydantic.ValidationError):
        MyNextFilter(owner="wrong_owner")


def test_owner_metadata_serialize_deserialize(test_owner_metadata):
    test_owner_metadata = _TestOwnerMetadata.model_validate(test_owner_metadata)
    data = test_owner_metadata.model_dump()
    deserialized_data = OwnerMetadata.model_validate(data)
    assert len(_TestOwnerMetadata.model_fields) > len(
        OwnerMetadata.model_fields
    )  # ensure extra data is available in _TestOwnerMetadata -> needed for RPC
    assert deserialized_data.model_dump() == data
