# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
"""Draft tests: what director-v2 sees when swarm rejects a task with ENOSPC.

2026-11-17 disk-full incident: dy-sidecar swarm tasks died instantly on
osparc-master-06 (placement rejections on the disk-full node; the
`mkdir /docker/overlay2/<id>-init: no space left on device` `Err` is logged
directly for `cc-*` tasks rejected there at 10:17 UTC).
Swarm re-attempted (tasks 1-3 rejected 09:08:35-09:09:02, the 4th booted at
09:09:13); the node was reported FAILED on the first rejected sample and the
cause was visible only while the *latest* task was still the rejected one.

These tests pin the current extraction behavior; the retention/grace-window
fix is ticket P1 in the tracker.
"""

from unittest.mock import AsyncMock

import pytest
from models_library.services_enums import ServiceState
from pytest_mock import MockerFixture
from simcore_service_director_v2.modules.dynamic_sidecar.docker_api import (
    get_dynamic_sidecar_state,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_states import (
    extract_task_state,
)

_ENOSPC_ERR = (
    "mkdir /docker/overlay2/dd42e9c1f3a2b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2"
    "-init: no space left on device"
)


def test_rejected_enospc_task_maps_to_failed_with_reason() -> None:
    service_state, message = extract_task_state({"State": "rejected", "Err": _ENOSPC_ERR})
    assert service_state == ServiceState.FAILED
    assert "no space left on device" in message


@pytest.fixture
def latest_task_mock(mocker: MockerFixture) -> AsyncMock:
    target = "simcore_service_director_v2.modules.dynamic_sidecar.docker_api._core._get_service_latest_task"
    return mocker.patch(target, autospec=True)


async def test_rejected_task_reports_failed_with_reason(
    latest_task_mock: AsyncMock,
) -> None:
    # Pins: while the latest task is the rejected one, the caller gets
    # (FAILED, ENOSPC message)
    latest_task_mock.return_value = {"Status": {"State": "rejected", "Err": _ENOSPC_ERR}}

    service_state, message = await get_dynamic_sidecar_state("dy-sidecar_5a4e3b2a1c0d4e5f8b9a0c1d2e3f4a5b")
    assert service_state == ServiceState.FAILED
    assert "no space left on device" in message


async def test_reason_lost_once_swarm_schedules_next_attempt(
    latest_task_mock: AsyncMock,
) -> None:
    # Pins the gap P1 addresses: swarm re-attempts replace the latest task, and
    # with it the reported reason goes back to empty
    latest_task_mock.return_value = {"Status": {"State": "rejected", "Err": _ENOSPC_ERR}}
    _, first_message = await get_dynamic_sidecar_state("dy-sidecar_test")

    latest_task_mock.return_value = {"Status": {"State": "pending", "Err": ""}}
    service_state, message = await get_dynamic_sidecar_state("dy-sidecar_test")

    assert "no space left on device" in first_message
    assert service_state == ServiceState.PENDING
    assert message == "", "the ENOSPC cause is no longer visible to callers"
