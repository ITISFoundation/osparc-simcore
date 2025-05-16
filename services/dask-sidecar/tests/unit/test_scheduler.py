# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member

import time

import distributed
import pytest
from dask_task_models_library.models import TASK_LIFE_CYCLE_EVENT

pytest_simcore_core_services_selection = [
    "rabbit",
]


def test_scheduler(dask_client: distributed.Client) -> None:
    def _some_task() -> int:
        time.sleep(1)
        return 2

    def _some_failing_task() -> None:
        time.sleep(1)
        msg = "Some error"
        raise RuntimeError(msg)

    future = dask_client.submit(_some_task)
    assert future.result(timeout=10) == 2

    events = dask_client.get_events(TASK_LIFE_CYCLE_EVENT.format(key=future.key))
    print("XXXX received events:")
    assert events
    assert isinstance(events, tuple)
    for event in events:
        print(f"\t{event}")

    future = dask_client.submit(_some_failing_task)
    with pytest.raises(RuntimeError):
        future.result(timeout=10)
    events = dask_client.get_events(TASK_LIFE_CYCLE_EVENT.format(key=future.key))
    print("XXXX received events:")
    assert events
    assert isinstance(events, tuple)
    for event in events:
        print(f"\t{event}")
