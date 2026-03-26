# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from dask_task_models_library.container_tasks.errors import (
    ServiceOutOfMemoryError,
    ServiceRuntimeError,
    ServiceTimeoutLoggingError,
    TaskCancelledError,
)
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import SimcorePlatformStatus
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.modules.comp_scheduler._scheduler_dask import (
    DaskScheduler,
)


@pytest.fixture
def fake_task() -> CompTaskAtDB:
    return CompTaskAtDB.model_validate(CompTaskAtDB.model_config["json_schema_extra"]["examples"][0])


@pytest.mark.parametrize(
    "exception, expected_error_type, expected_state",
    [
        pytest.param(
            ServiceOutOfMemoryError(
                service_key="simcore/services/comp/test",
                service_version="1.0.0",
                container_id="abc123",
                service_resources="2.0 GiB",
                service_logs=["Out of memory"],
            ),
            "runtime.oom",
            RunningState.FAILED,
            id="oom_error",
        ),
        pytest.param(
            ServiceTimeoutLoggingError(
                service_key="simcore/services/comp/test",
                service_version="1.0.0",
                container_id="abc123",
                timeout_timedelta="0:30:00",
            ),
            "runtime.timeout",
            RunningState.FAILED,
            id="timeout_error",
        ),
        pytest.param(
            ServiceRuntimeError(
                service_key="simcore/services/comp/test",
                service_version="1.0.0",
                container_id="abc123",
                exit_code=1,
                service_logs=["Segfault"],
            ),
            "runtime",
            RunningState.FAILED,
            id="generic_runtime_error",
        ),
        pytest.param(
            TaskCancelledError(),
            None,
            RunningState.ABORTED,
            id="cancelled_error",
        ),
    ],
)
async def test_handle_task_error_sets_correct_error_type(
    fake_task: CompTaskAtDB,
    exception: BaseException,
    expected_error_type: str | None,
    expected_state: RunningState,
):
    state, platform_status, errors, completed = await DaskScheduler._handle_task_error(  # noqa: SLF001
        task=fake_task,
        result=exception,
        log_error_context={},
    )

    assert state == expected_state
    assert platform_status == SimcorePlatformStatus.OK
    assert completed is True

    if expected_error_type is None:
        # TaskCancelledError returns no errors
        assert errors == []
    else:
        assert len(errors) == 1
        assert errors[0]["type"] == expected_error_type
        assert errors[0]["msg"]
        assert errors[0]["loc"] == (
            f"{fake_task.project_id}",
            f"{fake_task.node_id}",
        )
