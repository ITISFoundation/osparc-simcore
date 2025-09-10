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
