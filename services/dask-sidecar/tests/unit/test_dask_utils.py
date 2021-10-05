# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=no-member


import time
from typing import Any, Dict

import distributed
import pytest
from dask_task_models_library.container_tasks.events import TaskLogEvent
from simcore_service_dask_sidecar.boot_mode import BootMode
from simcore_service_dask_sidecar.dask_utils import (
    get_current_task_boot_mode,
    is_current_task_aborted,
    publish_event,
)


def test_publish_event(dask_client: distributed.Client):
    dask_pub = distributed.Pub("some_topic")
    dask_sub = distributed.Sub("some_topic")

    event_to_publish = TaskLogEvent(job_id="some_fake_job_id", log="the log")
    publish_event(dask_pub=dask_pub, event=event_to_publish)
    message = dask_sub.get(timeout=5)
    assert message is not None
    received_task_log_event = TaskLogEvent.parse_raw(message)
    assert received_task_log_event == event_to_publish


def test_task_is_aborted(dask_client: distributed.Client):
    def some_long_running_task() -> int:
        assert is_current_task_aborted() == False
        for i in range(300):
            time.sleep(1)
            if is_current_task_aborted():
                break
        assert is_current_task_aborted()
        return 12

    future = dask_client.submit(some_long_running_task)
    time.sleep(1)
    future.cancel()
    assert future.cancelled()


@pytest.mark.parametrize(
    "resources, expected_boot_mode",
    [
        ({"CPU": 2}, BootMode.CPU),
        ({"MPI": 1.0}, BootMode.MPI),
        ({"GPU": 5.0}, BootMode.GPU),
    ],
)
def test_task_boot_mode(
    dask_client: distributed.Client,
    resources: Dict[str, Any],
    expected_boot_mode: BootMode,
):
    future = dask_client.submit(get_current_task_boot_mode, resources=resources)
    received_boot_mode = future.result(timeout=1)
    assert received_boot_mode == expected_boot_mode
