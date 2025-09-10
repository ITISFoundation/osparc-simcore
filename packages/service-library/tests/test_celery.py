from typing import Literal

import pytest
from faker import Faker
from servicelib.celery.models import TaskFilter

_faker = Faker()


async def test_task_filter_serialization():
    _dict = {
        "string": _faker.word(),
        "int": _faker.random_int(),
        "bool": _faker.boolean(),
        "none": None,
        "uuid": _faker.uuid4(),
        "list": [_faker.word() for _ in range(3)],
    }
    task_filter = TaskFilter.model_validate(_dict)
    assert task_filter.model_dump() == _dict


@pytest.mark.parametrize("key_direction", ["plus", "minus"])
async def test_task_filter_sorting_key_not_serialized(
    key_direction: Literal["plus", "minus"],
):

    keys = ["a", "aa"]
    key = lambda s: len(s) if key_direction == "plus" else -len(s)

    task_filter = TaskFilter(
        a=_faker.random_int(),
        aa=_faker.word(),
        field_sorting_key=key,
    )
    expected_key = ":".join(
        [f"{k}={getattr(task_filter, k)}" for k in sorted(keys, key=key)]
    )
    assert task_filter._build_task_id_prefix() == expected_key
    assert "field_sorting_key" not in task_filter.model_dump()
