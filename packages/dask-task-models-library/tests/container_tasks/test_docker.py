import pytest
from dask_task_models_library.container_tasks.docker import DockerBasicAuth


@pytest.mark.parametrize("model_cls", [(DockerBasicAuth)])
def test_docker_models_examples(model_cls):
    examples = model_cls.model_config["json_schema_extra"]["examples"]

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = model_cls(**example)
        assert model_instance
