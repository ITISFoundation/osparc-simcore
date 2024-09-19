import pytest
from dask_task_models_library.container_tasks.protocol import (
    ContainerTaskParameters,
    TaskOwner,
)
from faker import Faker
from pydantic import ValidationError


@pytest.mark.parametrize("model_cls", [TaskOwner, ContainerTaskParameters])
def test_events_models_examples(model_cls):
    examples = model_cls.model_config["json_schema_extra"]["examples"]

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = model_cls(**example)
        assert model_instance


def test_task_owner_parent_valid(faker: Faker):
    invalid_task_owner_example = TaskOwner.model_config["json_schema_extra"][
        "examples"
    ][0]
    invalid_task_owner_example["parent_project_id"] = faker.uuid4()
    assert invalid_task_owner_example["parent_node_id"] is None
    with pytest.raises(ValidationError, match=r".+ are None or both are set!"):
        TaskOwner(**invalid_task_owner_example)

    invalid_task_owner_example["parent_project_id"] = None
    invalid_task_owner_example["parent_node_id"] = faker.uuid4()
    with pytest.raises(ValidationError, match=r".+ are None or both are set!"):
        TaskOwner(**invalid_task_owner_example)
