# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member

import time

import distributed
import pytest
from dask_task_models_library.models import TASK_LIFE_CYCLE_EVENT, TaskLifeCycleState
from models_library.projects_state import RunningState
from tenacity import Retrying, stop_after_delay, wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


def test_task_state_lifecycle(local_cluster: distributed.LocalCluster) -> None:
    def _some_task() -> int:
        time.sleep(1)
        return 2

    def _some_failing_task() -> None:
        time.sleep(1)
        msg = "Some error"
        raise RuntimeError(msg)

    local_cluster.scale(0)
    for attempt in Retrying(
        stop=stop_after_delay(10), wait=wait_fixed(1), reraise=True
    ):
        with attempt:
            assert len(local_cluster.workers) == 0
    with distributed.Client(local_cluster) as dask_client:
        # submit the task and wait until it goes into WAITING_FOR_RESOURCES
        future = dask_client.submit(_some_task, resources={"CPU": 1})
        for attempt in Retrying(
            stop=stop_after_delay(10), wait=wait_fixed(1), reraise=True
        ):
            with attempt:
                events = dask_client.get_events(
                    TASK_LIFE_CYCLE_EVENT.format(key=future.key)
                )
                assert isinstance(events, tuple)
                assert len(events) >= 2
                parsed_events = [
                    TaskLifeCycleState.model_validate(event[1]) for event in events
                ]
        assert parsed_events[0].state is RunningState.PENDING
        assert parsed_events[-1].state is RunningState.WAITING_FOR_RESOURCES

        # now add a worker and wait for it to take the task
        local_cluster.scale(1)

        # we basically wait for the tasks to finish
        assert future.result(timeout=15) == 2

        events = dask_client.get_events(TASK_LIFE_CYCLE_EVENT.format(key=future.key))
        assert isinstance(events, tuple)
        parsed_events = [
            TaskLifeCycleState.model_validate(event[1]) for event in events
        ]
        assert parsed_events[0].state is RunningState.PENDING
        assert RunningState.STARTED in {event.state for event in parsed_events}
        assert RunningState.FAILED not in {event.state for event in parsed_events}
        assert parsed_events[-1].state is RunningState.SUCCESS

        future = dask_client.submit(_some_failing_task)
        with pytest.raises(RuntimeError):
            future.result(timeout=10)
        events = dask_client.get_events(TASK_LIFE_CYCLE_EVENT.format(key=future.key))
        parsed_events = [
            TaskLifeCycleState.model_validate(event[1]) for event in events
        ]
        assert parsed_events[0].state is RunningState.PENDING
        assert RunningState.STARTED in {event.state for event in parsed_events}
        assert RunningState.FAILED in {event.state for event in parsed_events}
        assert RunningState.SUCCESS not in {event.state for event in parsed_events}
        assert parsed_events[-1].state is RunningState.FAILED
