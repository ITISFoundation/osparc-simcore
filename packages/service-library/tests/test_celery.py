from typing import Annotated

# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
import pydantic
import pytest
from faker import Faker
from pydantic import StringConstraints
from servicelib.celery.models import OwnerMetadata, TaskUUID, Wildcard

_faker = Faker()


class _TestOwnerMetadata(OwnerMetadata):
    string_: str
    int_: int
    bool_: bool
    none_: None
    uuid_: str
    list_: list[str]


@pytest.fixture
def owner_metadata() -> dict[str, str | int | bool | None | list[str]]:
    data = {
        "string_": _faker.word(),
        "int_": _faker.random_int(),
        "bool_": _faker.boolean(),
        "none_": None,
        "uuid_": _faker.uuid4(),
        "list_": [_faker.word() for _ in range(3)],
        "owner": _faker.word().lower(),
    }
    _TestOwnerMetadata.model_validate(data)  # ensure it's valid
    return data


async def test_task_filter_serialization(
    owner_metadata: dict[str, str | int | bool | None | list[str]],
):
    task_filter = _TestOwnerMetadata.model_validate(owner_metadata)
    assert task_filter.model_dump() == owner_metadata


async def test_task_filter_sorting_key_not_serialized():

    class _OwnerMetadata(OwnerMetadata):
        a: int | Wildcard
        b: str | Wildcard

    keys = ["a", "b", "owner"]
    task_filter = _OwnerMetadata.model_validate(
        {"a": _faker.random_int(), "b": _faker.word(), "owner": _faker.word().lower()}
    )
    expected_key = ":".join([f"{k}={getattr(task_filter, k)}" for k in sorted(keys)])
    assert task_filter._build_task_id_prefix() == expected_key


async def test_task_filter_task_uuid(
    owner_metadata: dict[str, str | int | bool | None | list[str]],
):
    task_filter = _TestOwnerMetadata.model_validate(owner_metadata)
    task_uuid = TaskUUID(_faker.uuid4())
    task_id = task_filter.create_task_id(task_uuid)
    assert OwnerMetadata.get_task_uuid(task_id=task_id) == task_uuid


async def test_create_task_filter_from_task_id():

    class MyModel(OwnerMetadata):
        _int: int
        _bool: bool
        _str: str
        _list: list[str]

    mymodel = MyModel(
        _int=1, _bool=True, _str="test", _list=["a", "b"], owner="myowner"
    )
    task_uuid = TaskUUID(_faker.uuid4())
    task_id = mymodel.create_task_id(task_uuid)
    assert OwnerMetadata.recreate_as_model(task_id=task_id, schema=MyModel) == mymodel


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
    class MyFilter(OwnerMetadata):
        extra_field: str

    with pytest.raises(pydantic.ValidationError):
        MyFilter(owner="", extra_field="value")

    with pytest.raises(pydantic.ValidationError):
        MyFilter(owner="UPPER_CASE", extra_field="value")

    class MyNextFilter(OwnerMetadata):
        owner: Annotated[
            str, StringConstraints(strip_whitespace=True, pattern=r"^the_task_owner$")
        ]

    with pytest.raises(pydantic.ValidationError):
        MyNextFilter(owner="wrong_owner")
