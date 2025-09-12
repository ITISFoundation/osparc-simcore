# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
import pydantic
import pytest
from faker import Faker
from pydantic import BaseModel
from servicelib.celery.models import TaskFilter, TaskUUID

_faker = Faker()


@pytest.fixture
def task_filter_data() -> dict[str, str | int | bool | None | list[str]]:
    return {
        "string": _faker.word(),
        "int": _faker.random_int(),
        "bool": _faker.boolean(),
        "none": None,
        "uuid": _faker.uuid4(),
        "list": [_faker.word() for _ in range(3)],
    }


async def test_task_filter_serialization(
    task_filter_data: dict[str, str | int | bool | None | list[str]],
):
    task_filter = TaskFilter.model_validate(task_filter_data)
    assert task_filter.model_dump() == task_filter_data
    assert task_filter.model_dump() == task_filter_data


async def test_task_filter_sorting_key_not_serialized():

    keys = ["a", "b"]
    task_filter = TaskFilter.model_validate(
        {
            "a": _faker.random_int(),
            "b": _faker.word(),
        }
    )
    expected_key = ":".join([f"{k}={getattr(task_filter, k)}" for k in sorted(keys)])
    assert task_filter._build_task_id_prefix() == expected_key


async def test_task_filter_task_uuid(
    task_filter_data: dict[str, str | int | bool | None | list[str]],
):
    task_filter = TaskFilter.model_validate(task_filter_data)
    task_uuid = TaskUUID(_faker.uuid4())
    task_id = task_filter.get_task_id(task_uuid)
    assert TaskFilter.get_task_uuid(task_id=task_id) == task_uuid


async def test_create_task_filter_from_task_id():

    class MyModel(BaseModel):
        _int: int
        _bool: bool
        _str: str
        _list: list[str]

    mymodel = MyModel(_int=1, _bool=True, _str="test", _list=["a", "b"])
    task_filter = TaskFilter.model_validate(mymodel.model_dump())
    task_uuid = TaskUUID(_faker.uuid4())
    task_id = task_filter.get_task_id(task_uuid)
    assert TaskFilter.recreate_model(task_id=task_id, model=MyModel) == mymodel


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
        TaskFilter.model_validate(bad_data)
