import pytest
from dask_task_models_library.container_tasks.errors import ServiceRuntimeError
from faker import Faker


def test_service_runtime_error_model(faker: Faker):
    with pytest.raises(
        ServiceRuntimeError,
        match=r"The service .+:.+ in container .+ failed with code \d+. Last logs:\n.*",
    ):
        raise ServiceRuntimeError(
            service_key=faker.word(),
            service_version=f"{faker.pyint()}.{faker.pyint()}.{faker.pyint()}",
            container_id=f"{faker.uuid4()}",
            exit_code=faker.pyint(),
            service_logs=faker.text(),
        )
