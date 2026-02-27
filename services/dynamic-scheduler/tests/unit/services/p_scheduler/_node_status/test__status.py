# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock, patch

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from simcore_service_dynamic_scheduler.services.p_scheduler._models import SchedulerServiceStatus
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._models import (
    ComponentPresence,
    ServicesPresence,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._status import get_scheduler_service_status

_A = ComponentPresence.ABSENT
_S = ComponentPresence.STARTING
_R = ComponentPresence.RUNNING
_F = ComponentPresence.FAILED

_IS_ABSENT = SchedulerServiceStatus.IS_ABSENT
_IS_PRESENT = SchedulerServiceStatus.IS_PRESENT
_TO_PRESENT = SchedulerServiceStatus.TRANSITION_TO_PRESENT
_TO_ABSENT = SchedulerServiceStatus.TRANSITION_TO_ABSENT
_IN_ERROR = SchedulerServiceStatus.IN_ERROR

_MODULE = "simcore_service_dynamic_scheduler.services.p_scheduler._node_status._status"


@pytest.fixture
def mocked_app() -> AsyncMock:
    return AsyncMock(spec=FastAPI)


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.mark.parametrize(
    "services_presence, user_services_presence, expected",
    [
        # --- legacy service cases ---
        (ServicesPresence(legacy=_A), None, _IS_ABSENT),
        (ServicesPresence(legacy=_S), None, _TO_PRESENT),
        (ServicesPresence(legacy=_R), None, _IS_PRESENT),
        (ServicesPresence(legacy=_F), None, _IN_ERROR),
        # --- new-style: sidecar ABSENT ---
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_A), _A, _IS_ABSENT),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_A), _S, _IS_ABSENT),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_A), _R, _IS_ABSENT),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_A), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_S), _A, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_S), _S, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_S), _R, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_S), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_R), _A, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_R), _S, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_R), _R, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_R), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_F), _A, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_F), _S, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_F), _R, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_A, dy_proxy=_F), _F, _IN_ERROR),
        # --- new-style: sidecar STARTING ---
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_A), _A, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_A), _S, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_A), _R, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_A), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_S), _A, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_S), _S, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_S), _R, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_S), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_R), _A, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_R), _S, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_R), _R, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_R), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_F), _A, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_F), _S, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_F), _R, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_S, dy_proxy=_F), _F, _IN_ERROR),
        # --- new-style: sidecar RUNNING ---
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_A), _A, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_A), _S, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_A), _R, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_A), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_S), _A, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_S), _S, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_S), _R, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_S), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_R), _A, _TO_ABSENT),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_R), _S, _TO_PRESENT),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_R), _R, _IS_PRESENT),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_R), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_F), _A, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_F), _S, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_F), _R, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_R, dy_proxy=_F), _F, _IN_ERROR),
        # --- new-style: sidecar FAILED ---
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_A), _A, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_A), _S, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_A), _R, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_A), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_S), _A, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_S), _S, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_S), _R, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_S), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_R), _A, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_R), _S, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_R), _R, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_R), _F, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_F), _A, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_F), _S, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_F), _R, _IN_ERROR),
        (ServicesPresence(dy_sidecar=_F, dy_proxy=_F), _F, _IN_ERROR),
    ],
)
async def test_get_scheduler_service_status(
    mocked_app: AsyncMock,
    node_id: NodeID,
    services_presence: ServicesPresence,
    user_services_presence: ComponentPresence | None,
    expected: SchedulerServiceStatus,
) -> None:
    mock_get_services = AsyncMock(return_value=services_presence)
    mock_get_user_services = AsyncMock(return_value=user_services_presence)

    with (
        patch(f"{_MODULE}.get_services_presence", mock_get_services),
        patch(f"{_MODULE}.get_user_services_presence", mock_get_user_services),
    ):
        assert await get_scheduler_service_status(mocked_app, node_id) == expected
