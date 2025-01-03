# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from models_library.docker import DockerGenericTag
from models_library.projects_state import RunningState
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.modules.comp_scheduler._utils import (
    COMPLETED_STATES,
    SCHEDULED_STATES,
    TASK_TO_START_STATES,
    create_service_resources_from_task,
)


@pytest.mark.parametrize(
    "state",
    [
        RunningState.PUBLISHED,
        RunningState.PENDING,
        RunningState.STARTED,
    ],
)
def test_scheduler_takes_care_of_runs_with_state(state: RunningState):
    assert state in SCHEDULED_STATES


@pytest.mark.parametrize(
    "state",
    [
        RunningState.SUCCESS,
        RunningState.ABORTED,
        RunningState.FAILED,
    ],
)
def test_scheduler_knows_these_are_completed_states(state: RunningState):
    assert state in COMPLETED_STATES


def test_scheduler_knows_all_the_states():
    assert COMPLETED_STATES.union(SCHEDULED_STATES).union(TASK_TO_START_STATES).union(
        {RunningState.NOT_STARTED, RunningState.UNKNOWN}
    ) == set(RunningState)


@pytest.mark.parametrize(
    "task",
    [
        CompTaskAtDB.model_validate(example)
        for example in CompTaskAtDB.model_config["json_schema_extra"]["examples"]
    ],
    ids=str,
)
def test_create_service_resources_from_task(task: CompTaskAtDB):
    received_service_resources = create_service_resources_from_task(task)
    assert received_service_resources
    assert len(received_service_resources) == 1
    assert "container" in received_service_resources
    service_resources = received_service_resources[DockerGenericTag("container")]
    assert service_resources.boot_modes == [task.image.boot_mode]
    assert service_resources.resources
    # some requirements are compulsory such as CPU,RAM
    assert "CPU" in service_resources.resources
    assert "RAM" in service_resources.resources
    # any set limit/reservation are the same
    for res_data in service_resources.resources.values():
        assert res_data.limit == res_data.reservation
    assert task.image.node_requirements
    assert service_resources.resources["CPU"].limit == task.image.node_requirements.cpu
    assert service_resources.resources["RAM"].limit == task.image.node_requirements.ram
    if task.image.node_requirements.gpu:
        assert "GPU" in service_resources.resources
        assert (
            service_resources.resources["GPU"].limit == task.image.node_requirements.gpu
        )
    else:
        assert "GPU" not in service_resources.resources

    if task.image.node_requirements.vram:
        assert "VRAM" in service_resources.resources
        assert (
            service_resources.resources["VRAM"].limit
            == task.image.node_requirements.vram
        )
    else:
        assert "VRAM" not in service_resources.resources
