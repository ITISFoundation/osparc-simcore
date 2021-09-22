import pytest
from dask_task_models_library.container_tasks.errors import ServiceRuntimeError


def test_service_runtime_error_model():
    with pytest.raises(
        ServiceRuntimeError,
        match=r"The service .+:.+ in container .+ failed with code \d+. Last logs:\n.*",
    ):
        raise ServiceRuntimeError(
            service_key="blah",
            service_version="2.2.2",
            container_id="123dfsd",
            exit_code=123,
            service_logs="This service failed\nbecause it is a test'\n",
        )
